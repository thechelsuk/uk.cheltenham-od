import { afterEach, beforeEach, describe, it } from "node:test";
import assert from "node:assert/strict";

import {
    FUEL_CSV_URL,
    RAW_REPO,
    dispatchDue,
    dispatchRaw,
    fuelCsv,
} from "../src/raw.js";

let realFetch;
let calls;
beforeEach(() => {
    realFetch = globalThis.fetch;
    calls = [];
    globalThis.fetch = async (url, init = {}) => {
        calls.push({ url: String(url), init });
        if (String(url) === FUEL_CSV_URL) {
            return new Response(
                "forecourt_update_timestamp,forecourts.node_id\n",
                { status: 200 },
            );
        }
        return new Response(null, { status: 204 });
    };
});
afterEach(() => {
    globalThis.fetch = realFetch;
});

describe("dispatchDue", () => {
    it("fires on every third 5-minute tick: :02, :17, :32 and :47", () => {
        const due = [2, 7, 12, 17, 22, 32, 47, 52].filter((m) =>
            dispatchDue(new Date(Date.UTC(2026, 10, 2, 11, m))),
        );
        assert.deepEqual(due, [2, 17, 32, 47]);
    });
});

describe("dispatchRaw", () => {
    it("starts the raw repo's capture workflow with its own token", async () => {
        const env = { RAW_GITHUB_TOKEN: "raw-token" };
        assert.equal(
            await dispatchRaw(env, new Date("2026-11-02T11:17:00Z")),
            204,
        );
        assert.equal(
            calls[0].url,
            `https://api.github.com/repos/${RAW_REPO}/actions/workflows/capture.yml/dispatches`,
        );
        assert.equal(calls[0].init.headers.Authorization, "Bearer raw-token");
        assert.deepEqual(JSON.parse(calls[0].init.body), { ref: "main" });
    });

    it("does nothing off the 15-minute ticks or without a token", async () => {
        assert.equal(
            await dispatchRaw(
                { RAW_GITHUB_TOKEN: "t" },
                new Date("2026-11-02T11:07:00Z"),
            ),
            null,
        );
        assert.equal(
            await dispatchRaw({}, new Date("2026-11-02T11:17:00Z")),
            null,
        );
        assert.equal(calls.length, 0);
    });

    it("throws when GitHub refuses, so the failure is logged", async () => {
        globalThis.fetch = async () => new Response(null, { status: 401 });
        await assert.rejects(
            dispatchRaw(
                { RAW_GITHUB_TOKEN: "t" },
                new Date("2026-11-02T11:17:00Z"),
            ),
            /HTTP 401/,
        );
    });
});

describe("fuelCsv", () => {
    const request = (token) =>
        new Request("https://w.example/raw/fuel.csv", {
            headers: token ? { Authorization: `Bearer ${token}` } : {},
        });

    it("passes the Fuel Finder CSV through for the capture workflow", async () => {
        const response = await fuelCsv(request("proxy-token"), {
            FUEL_PROXY_TOKEN: "proxy-token",
        });
        assert.equal(response.status, 200);
        assert.match(await response.text(), /^forecourt_update_timestamp/);
        assert.equal(calls[0].url, FUEL_CSV_URL);
    });

    it("refuses anyone without the token, so it is not an open proxy", async () => {
        const response = await fuelCsv(request("wrong"), {
            FUEL_PROXY_TOKEN: "proxy-token",
        });
        assert.equal(response.status, 401);
        assert.equal((await fuelCsv(request(null), {})).status, 401);
        assert.equal(calls.length, 0);
    });
});
