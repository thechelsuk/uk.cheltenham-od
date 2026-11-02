import { afterEach, beforeEach, describe, it } from "node:test";
import assert from "node:assert/strict";

import {
    RUNNERS,
    checkFetchers,
    failingHours,
    failingMessage,
    overdue,
} from "../src/fetch-status.js";

const NOW = new Date("2026-11-02T09:00:00Z");

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

function fakeEnv(state = {}) {
    return {
        STATE: fakeKV(state),
        GITHUB_REPO: "thechelsuk/uk.cheltenham-od",
        GITHUB_REF: "main",
    };
}

// What each runner's _data/fetch-status/<runner>.json holds on GitHub.
let files;
let calls;
let realFetch;
let sent;
const notify = async (_env, message) => {
    sent.push(message);
    return "ok";
};

beforeEach(() => {
    files = {};
    calls = [];
    sent = [];
    realFetch = globalThis.fetch;
    globalThis.fetch = async (url) => {
        url = String(url);
        calls.push(url);
        const runner = url.match(/fetch-status\/([^/]+)\.json$/)?.[1];
        if (runner && files[runner]) {
            return new Response(JSON.stringify(files[runner]), { status: 200 });
        }
        return new Response("404: Not Found", { status: 404 });
    };
});

afterEach(() => {
    globalThis.fetch = realFetch;
});

const planning = {
    last_ok: "2026-10-15",
    failing_since: "2026-10-15T12:00Z",
    last_error: "HTTPError: 403 Client Error: Forbidden",
};

describe("overdue", () => {
    it("lists scripts failing for more than 24 hours, longest first", () => {
        const scripts = {
            "_python/pi/planning.py": planning,
            "_python/post-office.py": {
                last_ok: "2026-11-01",
                failing_since: "2026-11-01T16:47Z",
                last_error: "Overpass timed out",
            },
            "_python/housing-supply.py": {
                last_ok: null,
                failing_since: "2026-10-22T19:51Z",
                last_error: "Could not find a link",
            },
            "_python/news.py": {
                last_ok: "2026-11-02",
                failing_since: null,
                last_error: null,
            },
        };
        assert.deepEqual(
            overdue(scripts, NOW).map((f) => f.script),
            ["_python/pi/planning.py", "_python/housing-supply.py"],
        );
    });
});

describe("failingHours", () => {
    it("allows the Pi's 5-minute scripts an hour and the workflows a day", () => {
        assert.equal(failingHours("pi"), 1);
        assert.equal(failingHours("refresh-weekly"), 24);
        assert.equal(failingHours("refresh-every-2-hours"), 24);
    });
});

describe("failingMessage", () => {
    it("names each script, since when, and its error, by email only", () => {
        const message = failingMessage(
            [{ script: "_python/pi/planning.py", ...planning }],
            1,
        );
        assert.equal(message.title, "Cheltenham OD: 1 data fetcher failing");
        assert.match(
            message.message,
            /_python\/pi\/planning\.py, failing since 2026-10-15 12:00 UTC: HTTPError: 403/,
        );
        assert.equal(message.light, undefined);
    });
});

describe("checkFetchers", () => {
    it("reads every runner's file and emails once about each failure", async () => {
        files.pi = {
            runner: "pi",
            scripts: { "_python/pi/planning.py": planning },
        };
        const env = fakeEnv();

        const result = await checkFetchers(env, NOW, notify);

        assert.deepEqual(
            calls,
            RUNNERS.map(
                (r) =>
                    `https://raw.githubusercontent.com/thechelsuk/uk.cheltenham-od/main/_data/fetch-status/${r}.json`,
            ),
        );
        assert.equal(result.failing, 1);
        assert.equal(sent.length, 1);
        assert.match(sent[0].message, /planning\.py/);

        // An hour later it is still failing: no second email.
        const later = new Date(NOW.getTime() + 61 * 60000);
        await checkFetchers(env, later, notify);
        assert.equal(sent.length, 1);
    });

    it("emails about a Pi script after an hour but a workflow script after a day", async () => {
        const twoHoursAgo = {
            last_ok: "2026-11-02",
            failing_since: "2026-11-02T07:00Z",
            last_error: "Timeout",
        };
        files.pi = {
            runner: "pi",
            scripts: { "_python/pi/rail-times.py": twoHoursAgo },
        };
        files["refresh-weekly"] = {
            runner: "refresh-weekly",
            scripts: { "_python/jobs.py": twoHoursAgo },
        };
        const result = await checkFetchers(fakeEnv(), NOW, notify);
        assert.deepEqual(result.emailed, ["_python/pi/rail-times.py"]);
    });

    it("checks at most once an hour", async () => {
        const env = fakeEnv({
            fetch_status_checked: "2026-11-02T08:30:00.000Z",
        });
        assert.equal(await checkFetchers(env, NOW, notify), null);
        assert.equal(calls.length, 0);
    });

    it("emails again if the script recovers and then fails again", async () => {
        files.pi = {
            runner: "pi",
            scripts: { "_python/pi/planning.py": planning },
        };
        const env = fakeEnv();
        await checkFetchers(env, NOW, notify);

        files.pi.scripts["_python/pi/planning.py"] = {
            last_ok: "2026-11-02",
            failing_since: null,
            last_error: null,
        };
        const t2 = new Date(NOW.getTime() + 61 * 60000);
        await checkFetchers(env, t2, notify);

        files.pi.scripts["_python/pi/planning.py"] = {
            ...planning,
            failing_since: "2026-11-02T10:00Z",
        };
        const t3 = new Date("2026-11-03T12:00:00Z");
        await checkFetchers(env, t3, notify);
        assert.equal(sent.length, 2);
    });

    it("ignores a runner whose file is missing or unreadable", async () => {
        files["refresh-monthly"] = "not an object";
        const env = fakeEnv();
        const result = await checkFetchers(env, NOW, notify);
        assert.equal(result.failing, 0);
        assert.equal(sent.length, 0);
    });
});

describe("scheduled", () => {
    it("runs the fetcher check alongside the Pi check", async () => {
        const { default: worker } = await import("../src/index.js");
        files.pi = {
            runner: "pi",
            scripts: { "_python/pi/planning.py": planning },
        };
        const env = {
            ...fakeEnv({ heartbeat: "2026-11-02T08:58:00.000Z" }),
            STALE_MINUTES: "12",
        };
        const sentBodies = [];
        env.NOTIFIER = {
            async fetch(_url, init) {
                sentBodies.push(JSON.parse(init.body));
                return new Response("{}", { status: 200 });
            },
        };
        const waits = [];
        await worker.scheduled({ scheduledTime: NOW.getTime() }, env, {
            waitUntil: (p) => waits.push(p),
        });
        await Promise.all(waits);
        assert.equal(waits.length, 2);
        assert.equal(sentBodies.length, 1);
        assert.match(sentBodies[0].title, /data fetcher failing/);
    });
});
