(function () {
    if (typeof Chart === "undefined") return;

    function read(id) {
        var el = document.getElementById(id);
        if (!el) return [];
        try {
            return JSON.parse(el.textContent || "[]");
        } catch (e) {
            return [];
        }
    }

    var months = read("ward-crime-months-data");
    var monthCanvas = document.getElementById("ward-crime-months");
    if (monthCanvas && months.length) {
        new Chart(monthCanvas, {
            type: "bar",
            data: {
                labels: months.map(function (m) { return m.month; }),
                datasets: [{ label: "Crimes reported", data: months.map(function (m) { return m.count; }) }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    y: { beginAtZero: true, ticks: { precision: 0 }, title: { display: true, text: "Crimes" } },
                },
            },
        });
    }

    var years = read("ward-price-years-data");
    var yearCanvas = document.getElementById("ward-price-years");
    if (yearCanvas && years.length) {
        new Chart(yearCanvas, {
            type: "line",
            data: {
                labels: years.map(function (y) { return y.year; }),
                datasets: [{
                    label: "Median sale price",
                    data: years.map(function (y) { return y.median; }),
                    borderWidth: 3,
                    tension: 0.25,
                    pointRadius: 2,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: { callback: function (v) { return "£" + v.toLocaleString("en-GB"); } },
                        title: { display: true, text: "Median price" },
                    },
                },
            },
        });
    }
})();
