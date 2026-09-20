(function () {
    var dataEl = document.getElementById("economy-data");
    if (!dataEl || typeof Chart === "undefined") return;

    var economy = null;
    try {
        economy = JSON.parse(dataEl.textContent);
    } catch (e) {
        return;
    }
    if (!economy) return;

    function line(label, values, thick) {
        return { label: label, data: values, borderWidth: thick ? 3 : 2, pointRadius: 0, tension: 0.2, fill: false, spanGaps: true };
    }

    function number(v) { return Math.round(v).toLocaleString("en-GB"); }

    var industryCanvas = document.getElementById("economy-industry-chart");
    if (industryCanvas && economy.jobs && economy.jobs.industries.length) {
        var industries = economy.jobs.industries;
        new Chart(industryCanvas, {
            type: "bar",
            data: {
                labels: industries.map(function (i) { return i.name; }),
                datasets: [
                    { label: "Cheltenham", data: industries.map(function (i) { return i.share; }) },
                    { label: "England", data: industries.map(function (i) { return i.england_share; }) },
                ],
            },
            options: {
                indexAxis: "y",
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: true },
                    tooltip: { callbacks: { label: function (ctx) { return ctx.dataset.label + ": " + ctx.parsed.x.toFixed(1) + "% of jobs"; } } },
                },
                scales: { x: { ticks: { callback: function (v) { return v + "%"; } } } },
            },
        });
    }

    var jobsCanvas = document.getElementById("economy-jobs-chart");
    if (jobsCanvas && economy.jobs && economy.jobs.series.length) {
        new Chart(jobsCanvas, {
            type: "line",
            data: {
                labels: economy.jobs.series.map(function (p) { return p.year; }),
                datasets: [line("Employee jobs", economy.jobs.series.map(function (p) { return p.jobs; }), true)],
            },
            options: {
                responsive: true,
                plugins: { legend: { display: false }, tooltip: { callbacks: { label: function (ctx) { return number(ctx.parsed.y) + " jobs"; } } } },
                scales: { y: { ticks: { callback: function (v) { return number(v); } } } },
            },
        });
    }

    var businessCanvas = document.getElementById("economy-business-chart");
    if (businessCanvas && economy.businesses && economy.businesses.series.length) {
        new Chart(businessCanvas, {
            type: "line",
            data: {
                labels: economy.businesses.series.map(function (p) { return p.year; }),
                datasets: [line("Businesses", economy.businesses.series.map(function (p) { return p.businesses; }), true)],
            },
            options: {
                responsive: true,
                plugins: { legend: { display: false }, tooltip: { callbacks: { label: function (ctx) { return number(ctx.parsed.y) + " businesses"; } } } },
                scales: { y: { ticks: { callback: function (v) { return number(v); } } } },
            },
        });
    }

    var claimantCanvas = document.getElementById("economy-claimant-chart");
    if (claimantCanvas && economy.claimants && economy.claimants.series.length) {
        var claimants = economy.claimants.series;
        new Chart(claimantCanvas, {
            type: "line",
            data: {
                labels: claimants.map(function (p) { return p.period; }),
                datasets: [
                    line("Cheltenham", claimants.map(function (p) { return p.rate; }), true),
                    line("England", claimants.map(function (p) { return p.england_rate; }), false),
                ],
            },
            options: {
                responsive: true,
                interaction: { mode: "index", intersect: false },
                plugins: {
                    legend: { display: true },
                    tooltip: { callbacks: { label: function (ctx) { return ctx.dataset.label + ": " + ctx.parsed.y.toFixed(1) + "%"; } } },
                },
                scales: { x: { ticks: { maxTicksLimit: 12 } }, y: { ticks: { callback: function (v) { return v + "%"; } } } },
            },
        });
    }
})();
