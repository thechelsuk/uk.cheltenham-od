(function () {
    const canvas = document.getElementById("fms-history-chart");
    const dataElement = document.getElementById("fms-history-months");
    if (!canvas || !dataElement || typeof Chart === "undefined") return;

    let months = [];
    try {
        months = JSON.parse(dataElement.textContent || "[]");
    } catch (e) {
        return;
    }

    new Chart(canvas, {
        type: "bar",
        data: {
            labels: months.map((m) => m.month),
            datasets: [
                {
                    label: "Reports",
                    data: months.map((m) => m.count),
                },
            ],
        },
        options: {
            responsive: true,
            plugins: { legend: { display: false } },
            scales: { y: { beginAtZero: true, ticks: { precision: 0 } } },
        },
    });
})();
