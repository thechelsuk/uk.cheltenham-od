(function () {
    const canvas = document.getElementById("affordability-chart");
    const dataElement = document.getElementById("affordability-data");
    if (!canvas || !dataElement || typeof Chart === "undefined") return;

    let years = [];
    try {
        years = JSON.parse(dataElement.textContent || "[]");
    } catch (e) {
        return;
    }
    if (!years.length) return;

    const series = [
        { label: "All homes", get: (y) => y.share, color: "#1d4e89", width: 3 },
        { label: "Flats", get: (y) => y.by_type.flat && y.by_type.flat.share, color: "#c2410c", width: 2 },
        { label: "Terraced", get: (y) => y.by_type.terraced && y.by_type.terraced.share, color: "#2f6b4f", width: 2 },
        { label: "Semi-detached", get: (y) => y.by_type.semi_detached && y.by_type.semi_detached.share, color: "#7a5195", width: 2 },
    ];

    new Chart(canvas, {
        type: "line",
        data: {
            labels: years.map((y) => y.year),
            datasets: series.map((s) => ({
                label: s.label,
                data: years.map(s.get),
                borderColor: s.color,
                backgroundColor: s.color,
                borderWidth: s.width,
                pointRadius: 2,
                tension: 0.25,
            })),
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: "index", intersect: false },
            scales: {
                y: {
                    beginAtZero: true,
                    title: { display: true, text: "Share of sales within reach (%)" },
                    ticks: { callback: (v) => v + "%" },
                },
            },
            plugins: {
                tooltip: { callbacks: { label: (c) => c.dataset.label + ": " + c.parsed.y + "%" } },
            },
        },
    });
})();
