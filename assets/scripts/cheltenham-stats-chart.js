(function () {
    var canvas = document.getElementById("population-chart");
    var dataEl = document.getElementById("population-series-data");
    if (!canvas || !dataEl || typeof Chart === "undefined") return;

    var series = [];
    try {
        series = JSON.parse(dataEl.textContent) || [];
    } catch (e) {
        return;
    }
    if (!series.length) return;

    new Chart(canvas, {
        type: "line",
        data: {
            labels: series.map(function (p) { return p.year; }),
            datasets: [
                {
                    label: "Population",
                    data: series.map(function (p) { return p.population; }),
                    borderWidth: 2,
                    tension: 0.2,
                    fill: false,
                },
            ],
        },
        options: {
            responsive: true,
            plugins: { legend: { display: false } },
            scales: {
                y: {
                    ticks: { callback: function (v) { return v.toLocaleString("en-GB"); } },
                },
            },
        },
    });
})();
