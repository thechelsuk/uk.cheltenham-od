(function () {
    if (typeof Chart === "undefined") return;

    function read(id) {
        const el = document.getElementById(id);
        if (!el) return [];
        try {
            return JSON.parse(el.textContent || "[]");
        } catch (e) {
            return [];
        }
    }

    const years = read("road-collisions-years-data");
    const yearCanvas = document.getElementById("road-collisions-years");
    if (yearCanvas && years.length) {
        new Chart(yearCanvas, {
            type: "bar",
            data: {
                labels: years.map((y) => y.year),
                datasets: [
                    { label: "Fatal", data: years.map((y) => y.fatal), backgroundColor: "#7f1d1d" },
                    { label: "Serious", data: years.map((y) => y.serious), backgroundColor: "#c2410c" },
                    { label: "Slight", data: years.map((y) => y.slight), backgroundColor: "#94a3b8" },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: { stacked: true },
                    y: { stacked: true, beginAtZero: true, ticks: { precision: 0 }, title: { display: true, text: "Collisions" } },
                },
            },
        });
    }

    const hours = read("road-collisions-hours-data");
    const hourCanvas = document.getElementById("road-collisions-hours");
    if (hourCanvas && hours.length) {
        new Chart(hourCanvas, {
            data: {
                labels: hours.map((h) => h.label),
                datasets: [
                    { type: "bar", label: "All collisions", data: hours.map((h) => h.collisions), backgroundColor: "#94a3b8" },
                    { type: "line", label: "Fatal or serious", data: hours.map((h) => h.ksi), borderColor: "#c2410c", backgroundColor: "#c2410c", tension: 0.25, pointRadius: 2 },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: { ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 12 } },
                    y: { beginAtZero: true, ticks: { precision: 0 }, title: { display: true, text: "Collisions, 2021 to 2025" } },
                },
            },
        });
    }
})();
