(function () {
    var el = document.getElementById("council-tax-stock-chart");
    var dataEl = document.getElementById("council-tax-stock-data");
    if (!el || !dataEl || typeof Chart === "undefined") return;

    var years = [];
    try {
        years = JSON.parse(dataEl.textContent) || [];
    } catch (e) {
        return;
    }
    if (!years.length) return;

    new Chart(el, {
        type: "line",
        data: {
            labels: years.map(function (y) { return y.year; }),
            datasets: [
                {
                    label: "Total properties",
                    data: years.map(function (y) { return y.all_properties; }),
                    fill: false,
                },
            ],
        },
        options: {
            responsive: true,
            plugins: { legend: { display: false } },
            scales: { y: { beginAtZero: false, ticks: { precision: 0 } } },
        },
    });
})();
