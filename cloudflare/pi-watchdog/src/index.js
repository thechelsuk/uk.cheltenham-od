// Pi watchdog for cheltenham-od.uk.
//
// The Raspberry Pi runs the 5-minute data scripts and starts the site's
// scheduled GitHub workflows. After each run where at least one script worked,
// it posts to /heartbeat. Every 5 minutes this Worker checks when the last
// heartbeat arrived. If the Pi has gone quiet for longer than STALE_MINUTES,
// Cloudflare takes over: it starts the fallback workflow, plus any scheduled
// workflow that has fallen due and hasn't run (see schedules.js), and asks the
// notifier Worker to email and turn the Hue light orange. The first heartbeat
// after that hands back to the Pi, and the light is restored.
//
// Once an hour it also emails about any data fetcher that has been failing for
// over a day (see fetch-status.js).
//
// A mode setting overrides the check: "auto" (the default) follows the
// heartbeat, "pi" never takes over, "cloud" always does.
//
// Routes:
//   POST /heartbeat   Bearer HEARTBEAT_TOKEN   record that the Pi finished a run
//   POST /mode        Bearer ADMIN_TOKEN       set the mode: body or ?mode= auto|pi|cloud
//   GET  /status                              the current state, as JSON

import { lastDue } from "./cron.js";
import { checkFetchers } from "./fetch-status.js";
import { SCHEDULES } from "./schedules.js";

export const MODES = ["auto", "pi", "cloud"];

// How far back to look for scheduled workflows the Pi may have missed.
const CATCH_UP_MINUTES = 30;

const KEY_HEARTBEAT = "heartbeat";
const KEY_MODE = "mode";
const KEY_ACTIVE = "cloud_active";
const KEY_DISPATCH = "last_dispatch";
const KEY_SCHEDULED = "scheduled:";

// Decide whether Cloudflare should be doing the Pi's work right now.
export function decide({ mode, lastHeartbeat, now, staleMinutes }) {
    if (mode === "pi") {
        return { active: false, reason: "mode is pi" };
    }
    if (mode === "cloud") {
        return { active: true, reason: "mode is cloud" };
    }
    if (!lastHeartbeat) {
        // Nothing to compare against until the Pi has pinged once, so a new
        // Worker doesn't take over before the Pi is set up.
        return { active: false, reason: "no heartbeat yet" };
    }
    const minutes = minutesSince(lastHeartbeat, now);
    if (minutes > staleMinutes) {
        return {
            active: true,
            reason: `the Pi last checked in ${minutes} minutes ago`,
        };
    }
    return {
        active: false,
        reason: `the Pi checked in ${minutes} minutes ago`,
    };
}

export function minutesSince(iso, now) {
    return Math.floor((now.getTime() - new Date(iso).getTime()) / 60000);
}

// Compare two strings in time that doesn't depend on where they differ.
export function safeEqual(a, b) {
    const enc = new TextEncoder();
    const x = enc.encode(String(a));
    const y = enc.encode(String(b));
    let diff = x.length ^ y.length;
    for (let i = 0; i < x.length; i++) {
        diff |= x[i] ^ (y[i % y.length] ?? 0);
    }
    return diff === 0;
}

function authorised(request, secret) {
    if (!secret) {
        return false;
    }
    const header = request.headers.get("Authorization") || "";
    const match = header.match(/^Bearer (.+)$/);
    return Boolean(match) && safeEqual(match[1], secret);
}

function json(body, status = 200) {
    return new Response(JSON.stringify(body, null, 2), {
        status,
        headers: { "Content-Type": "application/json" },
    });
}

async function readMode(env) {
    const mode = await env.STATE.get(KEY_MODE);
    return MODES.includes(mode) ? mode : "auto";
}

async function requestedMode(request, url) {
    const fromQuery = url.searchParams.get("mode");
    if (fromQuery) {
        return fromQuery.trim().toLowerCase();
    }
    const text = (await request.text()).trim();
    if (text.startsWith("{")) {
        try {
            return String(JSON.parse(text).mode || "")
                .trim()
                .toLowerCase();
        } catch {
            return "";
        }
    }
    return text.toLowerCase();
}

async function readJson(env, key) {
    return JSON.parse((await env.STATE.get(key)) || "null");
}

async function currentDecision(env, now) {
    return decide({
        mode: await readMode(env),
        lastHeartbeat: await env.STATE.get(KEY_HEARTBEAT),
        now,
        staleMinutes: Number(env.STALE_MINUTES),
    });
}

export async function status(env, now) {
    const lastHeartbeat = await env.STATE.get(KEY_HEARTBEAT);
    const decision = await currentDecision(env, now);
    const scheduled = {};
    for (const { workflow } of SCHEDULES) {
        scheduled[workflow] = await readJson(env, KEY_SCHEDULED + workflow);
    }
    return {
        mode: await readMode(env),
        cloud_active: decision.active,
        reason: decision.reason,
        last_heartbeat: lastHeartbeat,
        minutes_since_heartbeat: lastHeartbeat
            ? minutesSince(lastHeartbeat, now)
            : null,
        stale_after_minutes: Number(env.STALE_MINUTES),
        last_fallback: await readJson(env, KEY_DISPATCH),
        scheduled_started_by_cloudflare: scheduled,
    };
}

function githubHeaders(env) {
    return {
        Accept: "application/vnd.github+json",
        Authorization: `Bearer ${env.GITHUB_TOKEN}`,
        "User-Agent": "cheltenham-od-pi-watchdog",
        "X-GitHub-Api-Version": "2022-11-28",
    };
}

function workflowUrl(env, workflow) {
    return `https://api.github.com/repos/${env.GITHUB_REPO}/actions/workflows/${workflow}`;
}

export async function dispatchWorkflow(env, workflow) {
    const response = await fetch(`${workflowUrl(env, workflow)}/dispatches`, {
        method: "POST",
        headers: { ...githubHeaders(env), "Content-Type": "application/json" },
        body: JSON.stringify({ ref: env.GITHUB_REF }),
    });
    return { ok: response.ok, status: response.status };
}

// Whether the workflow has a run created at or after `since`.
export async function ranSince(env, workflow, since) {
    const created = encodeURIComponent(`>=${since.toISOString()}`);
    const response = await fetch(
        `${workflowUrl(env, workflow)}/runs?created=${created}&per_page=1`,
        { headers: githubHeaders(env) },
    );
    if (!response.ok) {
        throw new Error(
            `listing ${workflow} runs failed with HTTP ${response.status}`,
        );
    }
    return (await response.json()).total_count > 0;
}

// Start each scheduled workflow that was due since the Pi went quiet (within
// CATCH_UP_MINUTES) and has no run since it was due. Returns what it started.
export async function catchUp(env, now, lastHeartbeat) {
    const earliest = new Date(now.getTime() - CATCH_UP_MINUTES * 60000);
    const quietSince = lastHeartbeat ? new Date(lastHeartbeat) : earliest;
    const from = quietSince > earliest ? quietSince : earliest;
    const started = [];
    const failed = [];
    for (const { cron, workflow } of SCHEDULES) {
        const due = lastDue(cron, from, now);
        if (
            !due ||
            (await ranSince(env, workflow, new Date(due.getTime() - 60000)))
        ) {
            continue;
        }
        const result = await dispatchWorkflow(env, workflow);
        await env.STATE.put(
            KEY_SCHEDULED + workflow,
            JSON.stringify({
                at: now.toISOString(),
                due: due.toISOString(),
                ...result,
            }),
        );
        if (result.ok) {
            started.push(workflow);
        } else {
            failed.push(`${workflow} (HTTP ${result.status})`);
        }
    }
    if (failed.length) {
        throw new Error(`workflow_dispatch failed: ${failed.join(", ")}`);
    }
    return started;
}

// Ask the notifier Worker to email and set the light. Never throws: an alert
// failing mustn't stop the data work.
export async function notify(env, { title, message, light }) {
    if (!env.NOTIFIER) {
        return "no notifier bound";
    }
    try {
        const response = await env.NOTIFIER.fetch("https://notifier/notify", {
            method: "POST",
            headers: {
                Authorization: `Bearer ${env.NOTIFY_TOKEN}`,
                "Content-Type": "application/json",
            },
            body: JSON.stringify({ title, message, light }),
        });
        return response.ok ? "ok" : `HTTP ${response.status}`;
    } catch (err) {
        console.error(err);
        return `failed: ${err.message}`;
    }
}

function takeoverMessage(decision, lastHeartbeat) {
    const since = lastHeartbeat
        ? ` The last check-in was at ${lastHeartbeat}.`
        : "";
    return {
        title: "Cheltenham OD: Cloudflare has taken over from the Pi",
        message: `Cloudflare is running the 5-minute data checks and any scheduled workflows that fall due, because ${decision.reason}.${since}\n\nIt hands back as soon as the Pi checks in again.`,
        light: "orange",
    };
}

function handbackMessage(decision) {
    return {
        title: "Cheltenham OD: the Pi is back",
        message: `The Pi is running the data checks again (${decision.reason}). Cloudflare has stopped.`,
        light: "restore",
    };
}

// The 5-minute check.
export async function runCheck(env, now) {
    const lastHeartbeat = await env.STATE.get(KEY_HEARTBEAT);
    const decision = await currentDecision(env, now);
    const wasActive = (await env.STATE.get(KEY_ACTIVE)) === "true";

    let notified = null;
    if (decision.active !== wasActive) {
        await env.STATE.put(KEY_ACTIVE, String(decision.active));
        notified = await notify(
            env,
            decision.active
                ? takeoverMessage(decision, lastHeartbeat)
                : handbackMessage(decision),
        );
    }
    if (!decision.active) {
        return { ...decision, notified };
    }

    const result = await dispatchWorkflow(env, env.FALLBACK_WORKFLOW);
    await env.STATE.put(
        KEY_DISPATCH,
        JSON.stringify({
            at: now.toISOString(),
            ...result,
            reason: decision.reason,
        }),
    );
    const started = await catchUp(env, now, lastHeartbeat);
    if (!result.ok) {
        // Thrown so the failed run shows in the Worker's Cloudflare logs.
        throw new Error(
            `fallback workflow_dispatch failed with HTTP ${result.status}`,
        );
    }
    return { ...decision, notified, fallback: result, started };
}

export default {
    async fetch(request, env) {
        const url = new URL(request.url);
        const now = new Date();

        if (url.pathname === "/heartbeat" && request.method === "POST") {
            if (!authorised(request, env.HEARTBEAT_TOKEN)) {
                return json({ error: "unauthorised" }, 401);
            }
            await env.STATE.put(KEY_HEARTBEAT, now.toISOString());
            return new Response(null, { status: 204 });
        }

        if (url.pathname === "/mode" && request.method === "POST") {
            if (!authorised(request, env.ADMIN_TOKEN)) {
                return json({ error: "unauthorised" }, 401);
            }
            const mode = await requestedMode(request, url);
            if (!MODES.includes(mode)) {
                return json(
                    { error: `mode must be one of ${MODES.join(", ")}` },
                    400,
                );
            }
            await env.STATE.put(KEY_MODE, mode);
            return json(await status(env, now));
        }

        if (url.pathname === "/status" && request.method === "GET") {
            return json(await status(env, now));
        }

        return json({ error: "not found" }, 404);
    },

    async scheduled(controller, env, ctx) {
        const now = new Date(controller.scheduledTime);
        ctx.waitUntil(runCheck(env, now));
        // Hourly: email about data fetchers failing for over a day. Separate,
        // so a problem here never stops the takeover check.
        ctx.waitUntil(
            checkFetchers(env, now, notify).catch((err) => console.error(err)),
        );
    },
};
