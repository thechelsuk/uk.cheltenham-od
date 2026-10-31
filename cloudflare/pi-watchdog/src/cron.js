// Just enough cron to know when a schedule was due: five fields (minute, hour,
// day of month, month, day of week) with *, lists, ranges, steps and
// three-letter day names. Standard cron numbering: 0 or 7 = Sunday.
//
// Times are read in UK time (Europe/London), like the Pi's crontab, so a job
// set for 08:46 runs at 08:46 UK time in summer and winter alike.

export const TIME_ZONE = "Europe/London";

const WEEKDAY_NUMBERS = {
    Sun: 0,
    Mon: 1,
    Tue: 2,
    Wed: 3,
    Thu: 4,
    Fri: 5,
    Sat: 6,
};
const clock = new Intl.DateTimeFormat("en-GB", {
    timeZone: TIME_ZONE,
    hourCycle: "h23",
    minute: "numeric",
    hour: "numeric",
    day: "numeric",
    month: "numeric",
    weekday: "short",
});

// The minute, hour, day, month and weekday a UK clock shows at `date`.
export function ukFields(date) {
    const parts = Object.fromEntries(
        clock.formatToParts(date).map((p) => [p.type, p.value]),
    );
    return {
        minute: Number(parts.minute),
        hour: Number(parts.hour),
        day: Number(parts.day),
        month: Number(parts.month),
        weekday: WEEKDAY_NUMBERS[parts.weekday],
    };
}

const DAYS = { SUN: 0, MON: 1, TUE: 2, WED: 3, THU: 4, FRI: 5, SAT: 6 };
const RANGES = [
    [0, 59],
    [0, 23],
    [1, 31],
    [1, 12],
    [0, 7],
];

function value(text, field) {
    const name = text.toUpperCase();
    if (field === 4 && name in DAYS) {
        return DAYS[name];
    }
    const n = Number(text);
    if (!Number.isInteger(n)) {
        throw new Error(`bad cron value "${text}"`);
    }
    return n;
}

function parseField(text, field) {
    const [min, max] = RANGES[field];
    const allowed = new Set();
    for (const part of text.split(",")) {
        const [range, stepText] = part.split("/");
        const step = stepText ? Number(stepText) : 1;
        let start;
        let end;
        if (range === "*") {
            [start, end] = [min, max];
        } else if (range.includes("-")) {
            const [a, b] = range.split("-");
            [start, end] = [value(a, field), value(b, field)];
        } else {
            start = value(range, field);
            end = stepText ? max : start;
        }
        for (let n = start; n <= end; n += step) {
            allowed.add(field === 4 && n === 7 ? 0 : n);
        }
    }
    return allowed;
}

export function parse(expression) {
    const fields = expression.trim().split(/\s+/);
    if (fields.length !== 5) {
        throw new Error(`cron needs 5 fields: "${expression}"`);
    }
    return {
        sets: fields.map(parseField),
        anyDay: fields[2] === "*",
        anyWeekday: fields[4] === "*",
    };
}

export function matches(expression, date) {
    const { sets, anyDay, anyWeekday } = parse(expression);
    const [minute, hour, day, month, weekday] = sets;
    const uk = ukFields(date);
    if (!minute.has(uk.minute) || !hour.has(uk.hour) || !month.has(uk.month)) {
        return false;
    }
    const dayOk = day.has(uk.day);
    const weekdayOk = weekday.has(uk.weekday);
    // Cron's rule: if both day fields are restricted, either may match.
    if (!anyDay && !anyWeekday) {
        return dayOk || weekdayOk;
    }
    return dayOk && weekdayOk;
}

// The latest minute after `from` and up to `to` when the cron was due, or null.
export function lastDue(expression, from, to) {
    const start = Math.floor(from.getTime() / 60000) + 1;
    for (let m = Math.floor(to.getTime() / 60000); m >= start; m--) {
        const date = new Date(m * 60000);
        if (matches(expression, date)) {
            return date;
        }
    }
    return null;
}
