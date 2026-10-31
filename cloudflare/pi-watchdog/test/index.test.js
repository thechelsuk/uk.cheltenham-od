import { afterEach, beforeEach, describe, it } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

import worker, { catchUp, decide, runCheck, safeEqual } from "../src/index.js";
import { lastDue, matches } from "../src/cron.js";
import { SCHEDULES, WATCHDOG_CRON } from "../src/schedules.js";

const here = new URL(".", import.meta.url);
const repoFile = (path) =>
    readFileSync(new URL(`../../../${path}`, here), "utf8");

// A Thursday morning, 08:57 UTC.
const NOW = new Date("2026-10-29T08:57:00Z");

function minutesAgo(n) {
    return new Date(NOW.getTime() - n * 60000).toISOString();
}

// In-memory stand-in for the KV namespace binding.
function fakeKV(initial = {}) {
    const data = new Map(Object.entries(initial));
    return {
        data,
        async get(key) {
            return data.has(key) ? data.get(key) : null;
        },
        async put(key, value) {
            data.set(key, value);
        },
    };
}

// Stand-in for the service binding to cf-worker-notifier.
function fakeNotifier() {
    const sent = [];
    return {
        sent,
        async fetch(url, init) {
            sent.push({
                url,
                headers: init.headers,
                body: JSON.parse(init.body),
            });
            return new Response("{}", { status: 200 });
        },
    };
}

function fakeEnv(state = {}) {
    return {
        STATE: fakeKV(state),
        NOTIFIER: fakeNotifier(),
        GITHUB_REPO: "thechelsuk/uk.cheltenham-od",
        FALLBACK_WORKFLOW: "refresh-every-5-minutes.yml",
        GITHUB_REF: "main",
        STALE_MINUTES: "12",
        GITHUB_TOKEN: "gh-test",
        HEARTBEAT_TOKEN: "beat-test",
        ADMIN_TOKEN: "admin-test",
        NOTIFY_TOKEN: "notify-test",
    };
}

function request(path, { method = "GET", token, body } = {}) {
    const headers = token ? { Authorization: `Bearer ${token}` } : {};
    return new Request(`https://watchdog.example${path}`, {
        method,
        headers,
        body,
    });
}

// GitHub stand-in: dispatches succeed; workflows in `alreadyRan` report a run.
let calls;
let alreadyRan;
let dispatchStatus;
let realFetch;

const dispatches = () =>
    calls
        .filter((c) => c.url.endsWith("/dispatches"))
        .map((c) => c.url.match(/workflows\/([^/]+)\/dispatches/)[1]);

beforeEach(() => {
    calls = [];
    alreadyRan = new Set();
    dispatchStatus = 204;
    realFetch = globalThis.fetch;
    globalThis.fetch = async (url, init = {}) => {
        url = String(url);
        calls.push({ url, init });
        if (url.endsWith("/dispatches")) {
            return new Response(null, { status: dispatchStatus });
        }
        const runs = url.match(/workflows\/([^/]+)\/runs\?/);
        if (runs) {
            const count = alreadyRan.has(runs[1]) ? 1 : 0;
            return new Response(JSON.stringify({ total_count: count }), {
                status: 200,
            });
        }
        return new Response("unexpected", { status: 500 });
    };
});

afterEach(() => {
    globalThis.fetch = realFetch;
});

describe("decide", () => {
    const base = { now: NOW, staleMinutes: 12 };

    it("leaves the Pi alone while check-ins are fresh", () => {
        const d = decide({
            ...base,
            mode: "auto",
            lastHeartbeat: minutesAgo(4),
        });
        assert.equal(d.active, false);
    });

    it("takes over once the last check-in is older than the limit", () => {
        const d = decide({
            ...base,
            mode: "auto",
            lastHeartbeat: minutesAgo(13),
        });
        assert.equal(d.active, true);
        assert.match(d.reason, /13 minutes/);
    });

    it("does not take over at exactly the limit", () => {
        const d = decide({
            ...base,
            mode: "auto",
            lastHeartbeat: minutesAgo(12),
        });
        assert.equal(d.active, false);
    });

    it("waits for a first check-in before ever taking over", () => {
        const d = decide({ ...base, mode: "auto", lastHeartbeat: null });
        assert.equal(d.active, false);
    });

    it("never takes over in pi mode, always in cloud mode", () => {
        assert.equal(
            decide({ ...base, mode: "pi", lastHeartbeat: minutesAgo(600) })
                .active,
            false,
        );
        assert.equal(
            decide({ ...base, mode: "cloud", lastHeartbeat: minutesAgo(1) })
                .active,
            true,
        );
    });
});

describe("cron", () => {
    it("matches lists, ranges, steps and day names", () => {
        assert.equal(
            matches("17,47 * * * *", new Date("2026-10-29T08:47:00Z")),
            true,
        );
        assert.equal(
            matches("17,47 * * * *", new Date("2026-10-29T08:48:00Z")),
            false,
        );
        assert.equal(
            matches("36 */2 * * *", new Date("2026-10-29T08:36:00Z")),
            true,
        );
        assert.equal(
            matches("36 */2 * * *", new Date("2026-10-29T09:36:00Z")),
            false,
        );
        assert.equal(
            matches("2-59/5 * * * *", new Date("2026-10-29T08:57:00Z")),
            true,
        );
        assert.equal(
            matches("2-59/5 * * * *", new Date("2026-10-29T08:55:00Z")),
            false,
        );
        // 30 October 2026 is a Friday.
        assert.equal(
            matches("23 19 * * FRI", new Date("2026-10-30T19:23:00Z")),
            true,
        );
        assert.equal(
            matches("23 19 * * FRI", new Date("2026-10-29T19:23:00Z")),
            false,
        );
        assert.equal(
            matches("0 10 2 * *", new Date("2026-11-02T10:00:00Z")),
            true,
        );
    });

    it("reads times as UK time, in summer and winter", () => {
        // 08:46 UK time is 07:46 UTC in British Summer Time...
        assert.equal(
            matches("46 8 * * *", new Date("2026-07-15T07:46:00Z")),
            true,
        );
        assert.equal(
            matches("46 8 * * *", new Date("2026-07-15T08:46:00Z")),
            false,
        );
        // ...and 08:46 UTC in winter.
        assert.equal(
            matches("46 8 * * *", new Date("2026-12-15T08:46:00Z")),
            true,
        );
        // 23:30 UTC on Thursday 30 July is 00:30 on Friday 31 July in the UK.
        assert.equal(
            matches("30 0 31 * FRI", new Date("2026-07-30T23:30:00Z")),
            true,
        );
    });

    it("treats 0 and 7 as Sunday", () => {
        // 1 November 2026 is a Sunday.
        const sunday = new Date("2026-11-01T12:00:00Z");
        assert.equal(matches("0 12 * * 0", sunday), true);
        assert.equal(matches("0 12 * * 7", sunday), true);
        assert.equal(matches("0 12 * * SUN", sunday), true);
    });

    it("finds the latest due time after one moment, up to another", () => {
        const due = lastDue("17,47 * * * *", new Date(minutesAgo(30)), NOW);
        assert.equal(due.toISOString(), "2026-10-29T08:47:00.000Z");
        assert.equal(lastDue("46 8 * * *", new Date(minutesAgo(5)), NOW), null);
    });
});

describe("safeEqual", () => {
    it("matches equal strings only", () => {
        assert.equal(safeEqual("abc", "abc"), true);
        assert.equal(safeEqual("abc", "abd"), false);
        assert.equal(safeEqual("abc", "abcd"), false);
        assert.equal(safeEqual("abc", ""), false);
    });
});

describe("POST /heartbeat", () => {
    it("rejects a missing, wrong or admin token", async () => {
        const env = fakeEnv();
        for (const token of [undefined, "nope", "admin-test"]) {
            const res = await worker.fetch(
                request("/heartbeat", { method: "POST", token }),
                env,
            );
            assert.equal(res.status, 401);
        }
        assert.equal(env.STATE.data.has("heartbeat"), false);
    });

    it("records the time with the right token", async () => {
        const env = fakeEnv();
        const res = await worker.fetch(
            request("/heartbeat", { method: "POST", token: "beat-test" }),
            env,
        );
        assert.equal(res.status, 204);
        assert.ok(Date.parse(env.STATE.data.get("heartbeat")));
    });
});

describe("POST /mode", () => {
    it("rejects the heartbeat token", async () => {
        const env = fakeEnv();
        const res = await worker.fetch(
            request("/mode?mode=cloud", { method: "POST", token: "beat-test" }),
            env,
        );
        assert.equal(res.status, 401);
        assert.equal(env.STATE.data.has("mode"), false);
    });

    it("sets the mode from the query string, a plain body or JSON", async () => {
        const env = fakeEnv();
        const res = await worker.fetch(
            request("/mode?mode=cloud", {
                method: "POST",
                token: "admin-test",
            }),
            env,
        );
        assert.equal(res.status, 200);
        assert.equal((await res.json()).cloud_active, true);
        await worker.fetch(
            request("/mode", {
                method: "POST",
                token: "admin-test",
                body: "PI\n",
            }),
            env,
        );
        assert.equal(env.STATE.data.get("mode"), "pi");
        await worker.fetch(
            request("/mode", {
                method: "POST",
                token: "admin-test",
                body: '{"mode":"auto"}',
            }),
            env,
        );
        assert.equal(env.STATE.data.get("mode"), "auto");
    });

    it("refuses an unknown mode", async () => {
        const env = fakeEnv();
        const res = await worker.fetch(
            request("/mode?mode=off", { method: "POST", token: "admin-test" }),
            env,
        );
        assert.equal(res.status, 400);
        assert.equal(env.STATE.data.has("mode"), false);
    });
});

describe("GET /status", () => {
    it("reports the state without needing a token", async () => {
        const env = fakeEnv({ heartbeat: minutesAgo(20), mode: "banana" });
        const res = await worker.fetch(request("/status"), env);
        const body = await res.json();
        assert.equal(res.status, 200);
        assert.equal(body.mode, "auto");
        assert.equal(body.cloud_active, true);
        assert.equal(typeof body.minutes_since_heartbeat, "number");
        assert.ok("social-post.yml" in body.scheduled_started_by_cloudflare);
    });

    it("returns 404 for other routes", async () => {
        const res = await worker.fetch(request("/"), fakeEnv());
        assert.equal(res.status, 404);
    });
});

describe("runCheck", () => {
    it("does nothing while the Pi is healthy", async () => {
        const env = fakeEnv({ heartbeat: minutesAgo(3) });
        const result = await runCheck(env, NOW);
        assert.equal(result.active, false);
        assert.equal(calls.length, 0);
        assert.equal(env.NOTIFIER.sent.length, 0);
    });

    it("takes over: alerts once, runs the fallback and catches up", async () => {
        const env = fakeEnv({ heartbeat: minutesAgo(16) });
        const result = await runCheck(env, NOW);

        assert.equal(result.active, true);
        assert.equal(env.NOTIFIER.sent.length, 1);
        const alert = env.NOTIFIER.sent[0];
        assert.equal(alert.body.light, "orange");
        assert.match(alert.body.title, /taken over/);
        assert.equal(alert.headers.Authorization, "Bearer notify-test");
        // Fallback first, then what fell due after the Pi's last check-in at
        // 08:41: the social post (08:47) and the news digest (08:46).
        assert.deepEqual(dispatches(), [
            "refresh-every-5-minutes.yml",
            "social-post.yml",
            "news-digest-daily.yml",
        ]);
        const dispatch = calls.find((c) => c.url.endsWith("/dispatches"));
        assert.deepEqual(JSON.parse(dispatch.init.body), { ref: "main" });
        assert.equal(dispatch.init.headers.Authorization, "Bearer gh-test");
        const saved = JSON.parse(
            env.STATE.data.get("scheduled:social-post.yml"),
        );
        assert.equal(saved.due, "2026-10-29T08:47:00.000Z");
    });

    it("doesn't alert again on the next check", async () => {
        const env = fakeEnv({
            heartbeat: minutesAgo(16),
            cloud_active: "true",
        });
        await runCheck(env, NOW);
        assert.equal(env.NOTIFIER.sent.length, 0);
        assert.equal(dispatches()[0], "refresh-every-5-minutes.yml");
    });

    it("hands back to the Pi and restores the light", async () => {
        const env = fakeEnv({ heartbeat: minutesAgo(1), cloud_active: "true" });
        const result = await runCheck(env, NOW);
        assert.equal(result.active, false);
        assert.equal(env.NOTIFIER.sent[0].body.light, "restore");
        assert.match(env.NOTIFIER.sent[0].body.title, /Pi is back/);
        assert.equal(env.STATE.data.get("cloud_active"), "false");
        assert.equal(dispatches().length, 0);
    });

    it("keeps working if the notifier fails", async () => {
        const env = fakeEnv({ heartbeat: minutesAgo(16) });
        env.NOTIFIER.fetch = async () => {
            throw new Error("down");
        };
        const result = await runCheck(env, NOW);
        assert.match(result.notified, /failed: down/);
        assert.equal(dispatches()[0], "refresh-every-5-minutes.yml");
    });

    it("records and throws when GitHub refuses the fallback", async () => {
        dispatchStatus = 403;
        const env = fakeEnv({ mode: "cloud" });
        await assert.rejects(runCheck(env, NOW), /HTTP 403/);
        assert.equal(JSON.parse(env.STATE.data.get("last_dispatch")).ok, false);
    });

    it("runs from the cron handler at the scheduled time", async () => {
        const env = fakeEnv({ heartbeat: minutesAgo(30) });
        const pending = [];
        await worker.scheduled(
            { cron: WATCHDOG_CRON, scheduledTime: NOW.getTime() },
            env,
            {
                waitUntil: (p) => pending.push(p),
            },
        );
        await Promise.all(pending);
        assert.equal(dispatches()[0], "refresh-every-5-minutes.yml");
    });
});

describe("catchUp", () => {
    it("skips a workflow that already ran since it was due", async () => {
        alreadyRan.add("social-post.yml");
        const started = await catchUp(fakeEnv(), NOW, minutesAgo(16));
        assert.deepEqual(started, ["news-digest-daily.yml"]);
        assert.match(calls[0].url, /created=%3E%3D2026-10-29T08%3A46%3A00/);
    });

    it("only looks back to the Pi's last check-in", async () => {
        // Last check-in 08:50, after the 08:47 social post: the Pi handled it.
        const started = await catchUp(fakeEnv(), NOW, minutesAgo(7));
        assert.deepEqual(started, []);
        assert.equal(calls.length, 0);
    });

    it("looks back at most 30 minutes", async () => {
        // From 08:27: the social post (08:47, not 08:17 as well), the
        // two-hourly refresh (08:36) and the news digest (08:46).
        const started = await catchUp(fakeEnv(), NOW, minutesAgo(600));
        assert.deepEqual(started, [
            "social-post.yml",
            "refresh-every-2-hours.yml",
            "news-digest-daily.yml",
        ]);
    });

    it("throws after trying all when a dispatch fails", async () => {
        dispatchStatus = 500;
        await assert.rejects(
            catchUp(fakeEnv(), NOW, minutesAgo(16)),
            /social-post\.yml \(HTTP 500\)/,
        );
    });
});

describe("schedule config", () => {
    it("uses the cron in wrangler.toml", () => {
        const toml = readFileSync(new URL("../wrangler.toml", here), "utf8");
        assert.ok(toml.includes(`crons = ["${WATCHDOG_CRON}"]`));
    });

    it("lists the same schedules as the Pi's crontab", () => {
        const crontab = repoFile("_python/pi/crontab.txt");
        const lines = [
            ...crontab.matchAll(
                /^(\S+ \S+ \S+ \S+ \S+)\s+\$PI\/pi\/dispatch\.sh (\S+)/gm,
            ),
        ];
        assert.deepEqual(
            lines.map((m) => ({ cron: m[1], workflow: m[2] })),
            SCHEDULES,
        );
    });

    it("writes days of the week as names, not numbers", () => {
        for (const { cron } of SCHEDULES) {
            assert.match(cron.split(" ")[4], /^(\*|[A-Z]{3})$/, cron);
        }
    });

    it("starts each workflow only by dispatch, never a GitHub schedule", () => {
        const workflows = [
            "refresh-every-5-minutes.yml",
            ...SCHEDULES.map((s) => s.workflow),
        ];
        for (const workflow of workflows) {
            const yaml = repoFile(`.github/workflows/${workflow}`);
            assert.match(yaml, /^\s*workflow_dispatch:/m, workflow);
            assert.doesNotMatch(yaml, /^\s*schedule:/m, workflow);
        }
    });
});
