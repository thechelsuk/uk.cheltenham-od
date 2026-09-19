(function () {
    var performanceEl = document.getElementById("nhs-ae-performance-chart");
    var waitsEl = document.getElementById("nhs-ae-waits-chart");
    var dataEl = document.getElementById("nhs-ae-data");
    if (!dataEl || typeof Chart === "undefined") return;

    var months = [];
    try {
        months = JSON.parse(dataEl.textContent) || [];
    } catch (e) {
        return;
    }
    if (!months.length) return;

    // The data is newest first; charts read left to right, oldest first.
    months = months.slice().reverse();
    var labels = months.map(function (m) { return m.period; });

    function line(el, label, values, options) {
        if (!el) return;
        new Chart(el, {
            type: "line",
            data: { labels: labels, datasets: [{ label: label, data: values, fill: false, tension: 0.2 }] },
            options: Object.assign({ responsive: true, plugins: { legend: { display: false } } }, options),
        });
    }

    line(performanceEl, "Seen within 4 hours (%)", months.map(function (m) { return m.within_4hrs_pct; }), {
        scales: { y: { min: 0, max: 100, ticks: { callback: function (v) { return v + "%"; } } } },
    });
    line(waitsEl, "Waited 12+ hours from decision to admit", months.map(function (m) { return m.dta_12hrs; }), {
        scales: { y: { beginAtZero: true, ticks: { precision: 0 } } },
    });
})();
