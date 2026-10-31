// The site's scheduled GitHub workflows. The Pi starts them on time from its
// crontab (_python/pi/crontab.txt); while the Pi is down, the watchdog starts
// any that fall due. A test keeps this list and the crontab identical.
//
// Standard cron in UK time (as the Pi's clock), with day names (MON, FRI)
// rather than numbers. src/cron.js reads them in Europe/London.

// The watchdog's own check: two minutes after each Pi run (:00, :05 ...).
// Cloudflare runs it in UTC, which makes no difference every 5 minutes.
export const WATCHDOG_CRON = "2-59/5 * * * *";

export const SCHEDULES = [
    { cron: "17,47 * * * *", workflow: "social-post.yml" },
    { cron: "36 */2 * * *", workflow: "refresh-every-2-hours.yml" },
    { cron: "47 3,7,13,16 * * *", workflow: "refresh-4-times-daily.yml" },
    { cron: "29 6 * * *", workflow: "crime-backfill-check.yml" },
    { cron: "46 8 * * *", workflow: "news-digest-daily.yml" },
    { cron: "23 4 * * MON", workflow: "refresh-weekly.yml" },
    { cron: "23 19 * * FRI", workflow: "codeql.yml" },
    { cron: "13 20 * * FRI", workflow: "link-checker.yml" },
    { cron: "17 0 2 * *", workflow: "refresh-monthly.yml" },
    { cron: "0 10 2 * *", workflow: "data-refresh-reminder.yml" },
];
