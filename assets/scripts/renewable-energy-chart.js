(function () {
    var el = document.getElementById("renewable-energy-chart");
    var dataEl = document.getElementById("renewable-energy-data");
    if (!el || !dataEl || typeof Chart === "undefined") return;

    var years = [];
    try {
        years = JSON.parse(dataEl.textContent) || [];
    } catch (e) {
        return;
    }
    if (!years.length) return;

    new Chart(el, {
        type: "bar",
        data: {
            labels: years.map(function (y) { return y.year; }),
            datasets: [
                {
                    label: "Installed capacity (MW)",
                    data: years.map(function (y) { return y.capacity_mw; }),
                },
            ],
        },
        options: {
            responsive: true,
            plugins: { legend: { display: false } },
            scales: { y: { beginAtZero: true, title: { display: true, text: "MW" } } },
        },
    });
})();
