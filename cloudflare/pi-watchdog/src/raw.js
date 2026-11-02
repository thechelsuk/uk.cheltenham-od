// The raw data archive, thechelsuk/uk.cheltenham-od.raw.
//
// Its capture workflow saves the raw downloads behind the site's histories.
// GitHub's own schedule can run late or skip, so this Worker starts it every
// 15 minutes instead. Fuel Finder refuses GitHub's runners but not Cloudflare,
// so the workflow gets the fuel CSV through /raw/fuel.csv here, which needs
// FUEL_PROXY_TOKEN so it isn't an open proxy.

import { authorised } from "./auth.js";

export const RAW_REPO = "thechelsuk/uk.cheltenham-od.raw";
const RAW_WORKFLOW = "capture.yml";

export const FUEL_CSV_URL =
    "https://www.fuel-finder.service.gov.uk/internal/v1.0.2/csv/get-latest-fuel-prices-csv";

// The cron runs every 5 minutes from :02; every third tick is :02, :17, :32, :47.
export function dispatchDue(now) {
    return Math.floor(now.getUTCMinutes() / 5) % 3 === 0;
}

// Start the capture workflow when due. Returns GitHub's status, or null when
// not due or no token is set.
export async function dispatchRaw(env, now) {
    if (!env.RAW_GITHUB_TOKEN || !dispatchDue(now)) {
        return null;
    }
    const response = await fetch(
        `https://api.github.com/repos/${RAW_REPO}/actions/workflows/${RAW_WORKFLOW}/dispatches`,
        {
            method: "POST",
            headers: {
                Accept: "application/vnd.github+json",
                Authorization: `Bearer ${env.RAW_GITHUB_TOKEN}`,
                "Content-Type": "application/json",
                "User-Agent": "cheltenham-od-pi-watchdog",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            body: JSON.stringify({ ref: "main" }),
        },
    );
    if (!response.ok) {
        throw new Error(
            `raw capture dispatch failed with HTTP ${response.status}`,
        );
    }
    return response.status;
}

// GET /raw/fuel.csv: the latest Fuel Finder CSV, passed straight through.
export async function fuelCsv(request, env) {
    if (!authorised(request, env.FUEL_PROXY_TOKEN)) {
        return new Response("unauthorised\n", { status: 401 });
    }
    const upstream = await fetch(FUEL_CSV_URL, {
        headers: {
            "User-Agent":
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            Referer: "https://www.gov.uk/guidance/access-fuel-price-data",
        },
    });
    return new Response(upstream.body, {
        status: upstream.status,
        headers: { "Content-Type": "text/csv; charset=utf-8" },
    });
}
