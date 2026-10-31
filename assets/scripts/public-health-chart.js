(function () {
    var dataEl = document.getElementById("life-expectancy-data");
    var canvas = document.getElementById("life-expectancy-chart");
    if (!dataEl || !canvas || typeof Chart === "undefined") return;

    var series = [];
    try {
        series = JSON.parse(dataEl.textContent) || [];
    } catch (e) {
        return;
    }
    if (!series.length) return;

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

    function years(v) { return v.toFixed(1) + " years"; }

    new Chart(canvas, {
        type: "line",
        data: {
            labels: series.map(function (p) { return p.year; }),
            datasets: [
                line("Cheltenham men", "male", true),
                line("Cheltenham women", "female", true),
                line("England men", "england_male", false),
                line("England women", "england_female", false),
            ],
        },
        options: {
            responsive: true,
            interaction: { mode: "index", intersect: false },
            plugins: {
                legend: { display: true },
                tooltip: { callbacks: { label: function (ctx) { return ctx.dataset.label + ": " + years(ctx.parsed.y); } } },
            },
            scales: { y: { ticks: { callback: function (v) { return v + " years"; } } } },
        },
    });
})();
