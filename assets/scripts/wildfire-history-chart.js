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

    function stacked(canvasId, rows, labelKey, axisTitle) {
        const canvas = document.getElementById(canvasId);
        if (!canvas || !rows.length) return;
        new Chart(canvas, {
            type: "bar",
            data: {
                labels: rows.map((r) => r[labelKey]),
                datasets: [
                    { label: "Cheltenham", data: rows.map((r) => r.cheltenham) },
                    { label: "Surrounding area", data: rows.map((r) => r.surrounding) },
                ],
            },
            options: {
                scales: {
                    x: { stacked: true },
                    y: { stacked: true, beginAtZero: true, ticks: { precision: 0 }, title: { display: true, text: axisTitle } },
                },
            },
        });
    }

    stacked("wildfire-years", read("wildfire-years-data"), "year", "Fires");
    stacked("wildfire-months", read("wildfire-months-data"), "month", "Fires, all years");
})();
