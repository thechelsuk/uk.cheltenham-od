// Emails when a data fetcher keeps failing.
//
// _python/fetch_status.py records each script's last run in
// _data/fetch-status/<runner>.json: one file for the Pi and one per refresh
// workflow. Once an hour this reads them from GitHub and emails, through the
// notifier Worker, about any script that has been failing for longer than
// its runner's limit (failingHours). Each failure is emailed once; if the script recovers and fails again,
// that is a new failure and gets a new email.

// Must match RUNNERS in _python/fetch_status.py (a test there checks).
export const RUNNERS = [
    "pi",
    "refresh-every-2-hours",
    "refresh-4-times-daily",
    "refresh-weekly",
    "refresh-monthly",
];

// The Pi's scripts run every 5 minutes, so an hour of failures is already
// twelve missed runs. The workflows run every two hours at most.
// The raw data archive (src/raw.js) records its captures the same way.
export const RAW_STATUS_URL =
    "https://raw.githubusercontent.com/thechelsuk/uk.cheltenham-od.raw/main/status.json";
const RAW_PREFIX = "uk.cheltenham-od.raw: ";

export const FAILING_HOURS = { pi: 1, raw: 1 };
const DEFAULT_FAILING_HOURS = 24;

export function failingHours(runner) {
    return FAILING_HOURS[runner] ?? DEFAULT_FAILING_HOURS;
}
const CHECK_EVERY_MINUTES = 60;

const KEY_CHECKED = "fetch_status_checked";
const KEY_ALERTED = "fetch_status_alerted";

// "2026-10-15T12:00Z" as written by fetch_status.py.
const since = (iso) => new Date(iso);

// Scripts failing for longer than `hours`, longest first.
export function overdue(scripts, now, hours = DEFAULT_FAILING_HOURS) {
    return Object.entries(scripts)
        .filter(
            ([, r]) =>
                r?.failing_since &&
                now - since(r.failing_since) > hours * 3600000,
        )
        .map(([script, r]) => ({ script, ...r }))
        .sort((a, b) => since(a.failing_since) - since(b.failing_since));
}

function readable(iso) {
    return since(iso).toISOString().slice(0, 16).replace("T", " ") + " UTC";
}

export function failingMessage(fresh, total) {
    const s = total === 1 ? "" : "s";
    const lines = fresh.map(
        (f) =>
            `- ${f.script}, failing since ${readable(f.failing_since)}: ${f.last_error || "no error recorded"}`,
    );
    return {
        title: `Cheltenham OD: ${total} data fetcher${s} failing`,
        message: `${lines.join("\n")}\n\nThe workflows carry on past a failed script, so this is the only alert. The studio's Data Freshness tab has the full list.`,
    };
}

function runnerUrl(env, runner) {
    return `https://raw.githubusercontent.com/${env.GITHUB_REPO}/${env.GITHUB_REF}/_data/fetch-status/${runner}.json`;
}

async function readStatus(url) {
    try {
        const response = await fetch(url);
        if (!response.ok) {
            return {};
        }
        const data = await response.json();
        return data && typeof data.scripts === "object" ? data.scripts : {};
    } catch {
        return {};
    }
}

// The hourly check. Returns null when it isn't due yet.
export async function checkFetchers(env, now, notify) {
    const last = await env.STATE.get(KEY_CHECKED);
    if (last && now - new Date(last) < CHECK_EVERY_MINUTES * 60000) {
        return null;
    }
    await env.STATE.put(KEY_CHECKED, now.toISOString());

    const failures = [];
    for (const runner of RUNNERS) {
        const scripts = await readStatus(runnerUrl(env, runner));
        failures.push(...overdue(scripts, now, failingHours(runner)));
    }
    const raw = await readStatus(RAW_STATUS_URL);
    failures.push(
        ...overdue(raw, now, failingHours("raw")).map((f) => ({
            ...f,
            script: RAW_PREFIX + f.script,
        })),
    );
    failures.sort((a, b) => since(a.failing_since) - since(b.failing_since));
    const alerted = JSON.parse((await env.STATE.get(KEY_ALERTED)) || "{}");
    const fresh = failures.filter((f) => alerted[f.script] !== f.failing_since);
    // Keep only current failures, so a recovered script is forgotten.
    await env.STATE.put(
        KEY_ALERTED,
        JSON.stringify(
            Object.fromEntries(
                failures.map((f) => [f.script, f.failing_since]),
            ),
        ),
    );

    const notified = fresh.length
        ? await notify(env, failingMessage(fresh, failures.length))
        : null;
    return {
        failing: failures.length,
        emailed: fresh.map((f) => f.script),
        notified,
    };
}
