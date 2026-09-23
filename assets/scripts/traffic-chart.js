(function () {
    const dataElement = document.getElementById("traffic-days");
    if (!dataElement || typeof Chart === "undefined") return;

    let days = [];
    try {
        days = JSON.parse(dataElement.textContent || "[]");
    } catch (e) {
        return;
    }
    if (!days.length) return;

    const labels = days.map((d) => d.date.slice(5));

    function draw(id, label, values, options) {
        const canvas = document.getElementById(id);
        if (!canvas) return;
        new Chart(canvas, {
            type: "line",
            data: {
                labels: labels,
                datasets: [
                    {
                        label: label,
                        data: values,
                        borderWidth: 2,
                        fill: true,
                        pointRadius: 0,
                        pointHoverRadius: 4,
                        tension: 0.3,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: "index", intersect: false },
                plugins: { legend: { display: false } },
                scales: {
                    x: { grid: { display: false }, ticks: { maxTicksLimit: 8, maxRotation: 0 } },
                    y: Object.assign({ beginAtZero: true, ticks: { precision: 0 } }, options || {}),
                },
            },
        });
    }

    draw("traffic-uniques", "Unique visitors", days.map((d) => d.uniques));
    draw("traffic-requests", "Total requests", days.map((d) => d.requests));
    draw("traffic-cached", "Cached (%)", days.map((d) => d.cached_percent), { max: 100 });
})();
