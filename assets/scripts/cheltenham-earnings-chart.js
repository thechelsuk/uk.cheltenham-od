(function () {
    var dataEl = document.getElementById("earnings-series-data");
    if (!dataEl || typeof Chart === "undefined") return;

    var series = [];
    try {
        series = JSON.parse(dataEl.textContent) || [];
    } catch (e) {
        return;
    }
    if (!series.length) return;

    var labels = series.map(function (p) { return p.year; });

    function line(label, key, thick) {
        return {
            label: label,
            data: series.map(function (p) { return p[key]; }),
            borderWidth: thick ? 3 : 2,
            pointRadius: 0,
            tension: 0.2,
            fill: false,
            spanGaps: true,
        };
    }

    function pounds(v) { return "£" + Math.round(v).toLocaleString("en-GB"); }

    function options() {
        return {
            responsive: true,
            interaction: { mode: "index", intersect: false },
            plugins: {
                legend: { display: true },
                tooltip: { callbacks: { label: function (ctx) { return ctx.dataset.label + ": " + pounds(ctx.parsed.y); } } },
            },
            scales: { y: { ticks: { callback: function (v) { return pounds(v); } } } },
        };
    }

    var chart = document.getElementById("earnings-chart");
    if (chart) {
        new Chart(chart, {
            type: "line",
            data: {
                labels: labels,
                datasets: [
                    line("Cheltenham residents", "resident", true),
                    line("Cheltenham workplace", "workplace", false),
                    line("Gloucestershire", "gloucestershire", false),
                    line("South West", "south_west", false),
                    line("England", "england", false),
                ],
            },
            options: options(),
        });
    }

    var gender = document.getElementById("earnings-gender-chart");
    if (gender) {
        new Chart(gender, {
            type: "line",
            data: {
                labels: labels,
                datasets: [line("Men", "male", false), line("Women", "female", false)],
            },
            options: options(),
        });
    }
})();
