// One line for the takeover email saying whether GitHub itself is having
// problems, so a GitHub outage isn't mistaken for a fault on the Pi.
//
// Reads GitHub's public Statuspage summary. Only the parts the Pi depends on
// count: git (pull and push), the API (workflow dispatch) and Actions (the
// fallback), so a Copilot outage, say, still says to check the Pi.

export const GITHUB_STATUS_URL =
    "https://www.githubstatus.com/api/v2/summary.json";
const STATUS_PAGE = "https://www.githubstatus.com";
const PI_DEPENDS_ON = ["Git Operations", "API Requests", "Actions"];

// The summary, or null if it can't be read. Never throws: the takeover
// email must go out whatever GitHub's status page is doing.
export async function readGithubStatus() {
    try {
        const response = await fetch(GITHUB_STATUS_URL, {
            signal: AbortSignal.timeout(5000),
        });
        return response.ok ? await response.json() : null;
    } catch {
        return null;
    }
}

function utcTime(iso) {
    return new Date(iso).toISOString().slice(11, 16) + " UTC";
}

function joined(names) {
    return names.length > 1
        ? `${names.slice(0, -1).join(", ")} and ${names.at(-1)}`
        : names[0];
}

export function githubStatusLine(summary) {
    if (!Array.isArray(summary?.components)) {
        return `GitHub's status page couldn't be read, so check ${STATUS_PAGE}.`;
    }
    const affected = summary.components
        .filter(
            (c) => PI_DEPENDS_ON.includes(c.name) && c.status !== "operational",
        )
        .map((c) => c.name);
    if (!affected.length) {
        return "GitHub reports no problems, so check the Pi.";
    }
    const incident = (summary.incidents || []).find((i) =>
        affected.some((name) => i.name?.includes(name)),
    );
    const detail = incident
        ? ` ("${incident.name}", since ${utcTime(incident.created_at)})`
        : "";
    return `GitHub is having problems with ${joined(affected)}${detail}, so it's probably not the Pi. ${STATUS_PAGE}`;
}
