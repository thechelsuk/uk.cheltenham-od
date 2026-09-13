(function () {
    var canvas = document.getElementById("employment-chart");
    var dataEl = document.getElementById("employment-series-data");
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
                    label: "Economic activity rate",
                    data: series.map(function (p) { return p.economic_activity_rate; }),
                    borderWidth: 2,
                    tension: 0.2,
                    fill: false,
                },
                {
                    label: "Employment rate",
                    data: series.map(function (p) { return p.employment_rate; }),
                    borderWidth: 2,
                    tension: 0.2,
                    fill: false,
                },
                {
                    label: "Unemployment rate",
                    data: series.map(function (p) { return p.unemployment_rate; }),
                    borderWidth: 2,
                    tension: 0.2,
                    fill: false,
                    spanGaps: true,
                },
            ],
        },
        options: {
            responsive: true,
            plugins: { legend: { display: true } },
            scales: {
                y: {
                    ticks: { callback: function (v) { return v + "%"; } },
                },
            },
        },
    });
})();
