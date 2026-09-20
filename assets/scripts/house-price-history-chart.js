(function () {
    var priceCanvas = document.getElementById("land-registry-history-chart");
    var volumeCanvas = document.getElementById("land-registry-history-volume-chart");
    var historyEl = document.getElementById("house-price-history-data");
    var dataEl = document.getElementById("house-price-data");
    if (!priceCanvas || !historyEl || typeof Chart === "undefined") return;

    var history = [];
    var transactions = [];
    try {
        history = JSON.parse(historyEl.textContent) || [];
        transactions = dataEl ? JSON.parse(dataEl.textContent || "[]") : [];
    } catch (e) {
        return;
    }
    if (!history.length) return;

    var lastHistoryYear = history[history.length - 1].year;
    var currentYear = new Date().getFullYear();

    // Land Registry's type labels in the live data, mapped onto the history file's keys.
    var TYPE_KEYS = {
        "Detached": "detached",
        "Semi-detached": "semi_detached",
        "Terraced": "terraced",
        "Flat-maisonette": "flat",
    };
    var SERIES = [
        ["Detached", "detached"],
        ["Semi-detached", "semi_detached"],
        ["Terraced", "terraced"],
        ["Flat or maisonette", "flat"],
    ];

    function medianOf(values) {
        var sorted = values.slice().sort(function (a, b) { return a - b; });
        var mid = Math.floor(sorted.length / 2);
        return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
    }

    // The history file covers 1995 to its last year; later years come from the live transactions.
    var liveYears = {};
    transactions.forEach(function (t) {
        if (!t.amount || !t.date) return;
        var year = parseInt(t.date.slice(0, 4), 10);
        if (year <= lastHistoryYear) return;
        var entry = liveYears[year] || (liveYears[year] = { all: [], byType: {} });
        entry.all.push(t.amount);
        var key = TYPE_KEYS[t.property_type];
        if (key) (entry.byType[key] = entry.byType[key] || []).push(t.amount);
    });

    var years = history.map(function (y) {
        var byType = {};
        SERIES.forEach(function (s) { byType[s[1]] = y.by_type[s[1]] ? y.by_type[s[1]].median : null; });
        return { year: y.year, count: y.count, median: y.median, byType: byType };
    });
    Object.keys(liveYears).sort().forEach(function (year) {
        var entry = liveYears[year];
        var byType = {};
        SERIES.forEach(function (s) { byType[s[1]] = entry.byType[s[1]] ? medianOf(entry.byType[s[1]]) : null; });
        years.push({ year: parseInt(year, 10), count: entry.all.length, median: medianOf(entry.all), byType: byType });
    });

    var labels = years.map(function (y) { return y.year === currentYear ? y.year + " (part year)" : String(y.year); });

    function price(v) { return "£" + Math.round(v).toLocaleString("en-GB"); }

    function line(label, values, thick) {
        return { label: label, data: values, borderWidth: thick ? 3 : 2, pointRadius: 0, tension: 0.2, fill: false, spanGaps: true };
    }

    var datasets = [line("All sales", years.map(function (y) { return y.median; }), true)];
    SERIES.forEach(function (s) {
        datasets.push(line(s[0], years.map(function (y) { return y.byType[s[1]]; }), false));
    });

    new Chart(priceCanvas, {
        type: "line",
        data: { labels: labels, datasets: datasets },
        options: {
            responsive: true,
            interaction: { mode: "index", intersect: false },
            plugins: {
                legend: { display: true },
                tooltip: { callbacks: { label: function (ctx) { return ctx.dataset.label + ": " + price(ctx.parsed.y); } } },
            },
            scales: {
                x: { ticks: { maxTicksLimit: 12 } },
                y: { ticks: { callback: function (v) { return price(v); } } },
            },
        },
    });

    if (volumeCanvas) {
        new Chart(volumeCanvas, {
            type: "bar",
            data: { labels: labels, datasets: [{ label: "Sales", data: years.map(function (y) { return y.count; }) }] },
            options: {
                responsive: true,
                plugins: { legend: { display: false } },
                scales: { x: { ticks: { maxTicksLimit: 12 } }, y: { beginAtZero: true } },
            },
        });
    }
})();
