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

    var days = read("fuel-history-data");
    var ukWeeks = read("fuel-uk-data");
    if (!days.length) return;
    var labels = days.map(function (d) { return d.date; });

    // Each day takes the UK figure for the week it falls in (weeks start on Monday).
    function ukValue(date, key) {
        var match = null;
        ukWeeks.forEach(function (w) {
            var end = new Date(w.week + "T00:00:00Z");
            end.setUTCDate(end.getUTCDate() + 7);
            if (w.week <= date && date < end.toISOString().slice(0, 10)) match = w[key];
        });
        return match;
    }

    function chart(id, fuel, ukKey) {
        var canvas = document.getElementById(id);
        if (!canvas) return;
        function series(stat) {
            return days.map(function (d) { return d.fuels[fuel] ? d.fuels[fuel][stat] : null; });
        }
        new Chart(canvas, {
            type: "line",
            data: {
                labels: labels,
                datasets: [
                    // Palette slots as on the house price chart, skipping amber: blue and
                    // orange go to the local and UK averages, which run close together,
                    // and green and pink to the highest and cheapest, so no two lines
                    // rely on a red/green difference.
                    { label: "Highest", data: series("highest"), pointRadius: 0, borderWidth: 2, paletteSlot: 2 },
                    { label: "Average", data: series("average"), pointRadius: 0, borderWidth: 3, paletteSlot: 0 },
                    { label: "Cheapest", data: series("cheapest"), pointRadius: 0, borderWidth: 2, paletteSlot: 4 },
                    {
                        label: "UK average (weekly)",
                        data: labels.map(function (d) { return ukValue(d, ukKey); }),
                        pointRadius: 0,
                        borderWidth: 2,
                        stepped: true,
                        paletteSlot: 1,
                    },
                ],
            },
            options: {
                interaction: { mode: "index", intersect: false },
                spanGaps: true,
                scales: {
                    x: { ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 8 } },
                    y: { title: { display: true, text: "Pence per litre" } },
                },
            },
        });
    }

    chart("fuel-history-unleaded", "Unleaded", "unleaded");
    chart("fuel-history-diesel", "Diesel", "diesel");
})();
