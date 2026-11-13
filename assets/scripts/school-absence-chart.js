(function () {
    var dataEl = document.getElementById("school-absence-data");
    if (!dataEl || typeof Chart === "undefined") return;

    var series = [];
    try {
        series = JSON.parse(dataEl.textContent) || [];
    } catch (e) {
        return;
    }
    if (!series.length) return;

    // Leave a gap for years with no figures (2019/20), rather than joining
    // 2018/19 straight to 2020/21.
    var byYear = {};
    series.forEach(function (y) { byYear[y.year] = y; });
    var first = parseInt(series[0].year, 10);
    var last = parseInt(series[series.length - 1].year, 10);
    series = [];
    for (var start = first; start <= last; start++) {
        var label = start + "/" + String(start + 1).slice(2);
        series.push(byYear[label] || { year: label });
    }

    var labels = series.map(function (y) { return y.year; });

    function line(label, area, measure) {
        return {
            label: label,
            data: series.map(function (y) { return y[area] ? y[area][measure] : null; }),
            borderWidth: 2,
            pointRadius: 2,
            tension: 0.2,
            fill: false,
            spanGaps: false,
        };
    }

    function draw(id, measure) {
        var canvas = document.getElementById(id);
        if (!canvas) return;
        new Chart(canvas, {
            type: "line",
            data: {
                labels: labels,
                datasets: [
                    line("Gloucestershire", "gloucestershire", measure),
                    line("South West", "south_west", measure),
                    line("England", "england", measure),
                ],
            },
            options: {
                responsive: true,
                interaction: { mode: "index", intersect: false },
                plugins: {
                    legend: { display: true },
                    tooltip: {
                        callbacks: {
                            label: function (ctx) { return ctx.dataset.label + ": " + ctx.parsed.y.toFixed(1) + "%"; },
                        },
                    },
                },
                scales: {
                    y: { beginAtZero: true, ticks: { callback: function (v) { return v + "%"; } } },
                },
            },
        });
    }

    draw("absence-overall-chart", "overall");
    draw("absence-persistent-chart", "persistent");
    draw("absence-severe-chart", "severe");
})();
