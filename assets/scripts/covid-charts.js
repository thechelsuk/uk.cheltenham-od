(function () {
    if (typeof Chart === "undefined") return;

    var el = document.getElementById("covid-data");
    if (!el) return;
    var weekly;
    try {
        weekly = JSON.parse(el.textContent || "{}");
    } catch (e) {
        return;
    }

    // Every series shares one set of week labels, so charts with two series line up.
    var weeks = Array.from(
        new Set(Object.values(weekly).flatMap(function (series) {
            return series.map(function (w) { return w.week; });
        }))
    ).sort();

    function values(key) {
        var byWeek = {};
        (weekly[key] || []).forEach(function (w) { byWeek[w.week] = w.value; });
        return weeks.map(function (w) { return w in byWeek ? byWeek[w] : null; });
    }

    var xAxis = { ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 8 } };

    function chart(id, datasets, scales) {
        var canvas = document.getElementById(id);
        if (!canvas) return;
        new Chart(canvas, {
            data: { labels: weeks, datasets: datasets },
            options: {
                interaction: { mode: "index", intersect: false },
                scales: Object.assign({ x: xAxis }, scales),
            },
        });
    }

    function countAxis(title) {
        return { beginAtZero: true, ticks: { precision: 0 }, title: { display: true, text: title } };
    }

    function rightAxis(title) {
        return { position: "right", beginAtZero: true, grid: { drawOnChartArea: false }, title: { display: true, text: title } };
    }

    chart("covid-cases",
        [{ type: "bar", label: "Confirmed cases", data: values("cases") }],
        { y: countAxis("Cases per week") });

    chart("covid-testing",
        [
            { type: "bar", label: "PCR tests", data: values("tests"), yAxisID: "y", order: 2 },
            { type: "line", label: "Testing positive (%)", data: values("positivity"), yAxisID: "y1", pointRadius: 0, order: 1 },
        ],
        { y: countAxis("Tests per week"), y1: rightAxis("Testing positive (%)") });

    chart("covid-hospital",
        [
            { type: "bar", label: "Admissions", data: values("admissions"), yAxisID: "y", order: 2 },
            { type: "line", label: "Occupied beds (average)", data: values("beds"), yAxisID: "y1", pointRadius: 0, order: 1 },
        ],
        { y: countAxis("Admissions per week"), y1: rightAxis("Occupied beds") });

    chart("covid-deaths",
        [{ type: "bar", label: "Deaths", data: values("deaths") }],
        { y: countAxis("Deaths per week") });
})();
