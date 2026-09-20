(function () {
    var priceCanvas = document.getElementById("rents-price-chart");
    var changeCanvas = document.getElementById("rents-change-chart");
    var dataEl = document.getElementById("rents-series-data");
    if (!dataEl || typeof Chart === "undefined") return;

    var series = [];
    try {
        series = JSON.parse(dataEl.textContent) || [];
    } catch (e) {
        return;
    }
    if (!series.length) return;

    var labels = series.map(function (p) { return p.period; });

    function line(label, key) {
        return {
            label: label,
            data: series.map(function (p) { return p[key]; }),
            borderWidth: 2,
            pointRadius: 0,
            tension: 0.2,
            fill: false,
            spanGaps: true,
        };
    }

    function options(tick) {
        return {
            responsive: true,
            interaction: { mode: "index", intersect: false },
            plugins: {
                legend: { display: true },
                tooltip: { callbacks: { label: function (ctx) { return ctx.dataset.label + ": " + tick(ctx.parsed.y); } } },
            },
            scales: {
                x: { ticks: { maxTicksLimit: 12 } },
                y: { ticks: { callback: function (v) { return tick(v); } } },
            },
        };
    }

    if (priceCanvas) {
        new Chart(priceCanvas, {
            type: "line",
            data: {
                labels: labels,
                datasets: [
                    line("Cheltenham", "price"),
                    line("South West", "south_west"),
                    line("England", "england"),
                ],
            },
            options: options(function (v) { return "£" + Math.round(v).toLocaleString("en-GB"); }),
        });
    }

    if (changeCanvas) {
        new Chart(changeCanvas, {
            type: "line",
            data: {
                labels: labels,
                datasets: [
                    line("Cheltenham", "annual_change"),
                    line("South West", "south_west_annual_change"),
                    line("England", "england_annual_change"),
                ],
            },
            options: options(function (v) { return v.toFixed(1) + "%"; }),
        });
    }
})();
