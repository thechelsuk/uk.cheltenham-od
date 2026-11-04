import { afterEach, beforeEach, describe, it } from "node:test";
import assert from "node:assert/strict";

import {
    GITHUB_STATUS_URL,
    githubStatusLine,
    readGithubStatus,
} from "../src/github-status.js";

// Shaped like the Statuspage summary at githubstatus.com/api/v2/summary.json.
function summary({ components = {}, incidents = [] } = {}) {
    const names = [
        "Git Operations",
        "API Requests",
        "Actions",
        "Copilot",
        "Pages",
    ];
    return {
        components: names.map((name) => ({
            name,
            status: components[name] || "operational",
        })),
        incidents,
    };
}

const INCIDENT = {
    name: "Incident with Pull Requests, Git Operations and Issues",
    status: "investigating",
    created_at: "2026-11-04T09:49:12.000Z",
};

describe("githubStatusLine", () => {
    it("blames GitHub when git, the API or Actions are affected", () => {
        const line = githubStatusLine(
            summary({
                components: {
                    "Git Operations": "degraded_performance",
                    Actions: "partial_outage",
                },
                incidents: [INCIDENT],
            }),
        );
        assert.match(line, /^GitHub is having problems/);
        assert.match(line, /Git Operations and Actions/);
        assert.match(line, /Incident with Pull Requests/);
        assert.match(line, /since 09:49 UTC/);
        assert.match(line, /probably not the Pi/);
        assert.match(line, /https:\/\/www\.githubstatus\.com/);
    });

    it("blames GitHub without an incident name if none is open", () => {
        const line = githubStatusLine(
            summary({ components: { "API Requests": "major_outage" } }),
        );
        assert.match(line, /^GitHub is having problems with API Requests/);
        assert.doesNotMatch(line, /since/);
    });

    it("ignores problems the Pi doesn't depend on", () => {
        const line = githubStatusLine(
            summary({
                components: { Copilot: "major_outage" },
                incidents: [{ ...INCIDENT, name: "Copilot is down" }],
            }),
        );
        assert.match(line, /^GitHub reports no problems/);
        assert.match(line, /so check the Pi/);
    });

    it("says so when the status can't be read", () => {
        assert.match(githubStatusLine(null), /couldn't be read/);
        assert.match(githubStatusLine({}), /couldn't be read/);
    });
});

describe("readGithubStatus", () => {
    let realFetch;
    beforeEach(() => {
        realFetch = globalThis.fetch;
    });
    afterEach(() => {
        globalThis.fetch = realFetch;
    });

    it("reads the summary", async () => {
        let asked;
        globalThis.fetch = async (url) => {
            asked = String(url);
            return new Response(JSON.stringify(summary()), { status: 200 });
        };
        const data = await readGithubStatus();
        assert.equal(asked, GITHUB_STATUS_URL);
        assert.equal(data.components.length, 5);
    });

    it("returns null instead of throwing", async () => {
        globalThis.fetch = async () => new Response("down", { status: 503 });
        assert.equal(await readGithubStatus(), null);
        globalThis.fetch = async () => {
            throw new Error("network");
        };
        assert.equal(await readGithubStatus(), null);
    });
});
