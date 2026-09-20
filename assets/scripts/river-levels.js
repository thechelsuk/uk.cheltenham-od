(function () {
    var dataEl = document.getElementById("river-levels-data");
    if (!dataEl) return;

    var stations = [];
    var history = {};
    try {
        stations = JSON.parse(dataEl.textContent) || [];
        var historyEl = document.getElementById("river-levels-history-data");
        if (historyEl) history = JSON.parse(historyEl.textContent) || {};
    } catch (e) {
        return;
    }
    if (!stations.length) return;

    var STATUS_COLOURS = {
        "Above typical range": ["#c0392b", "#e74c3c"],
        "Below typical range": ["#2471a3", "#5dade2"],
        "Within typical range": ["#2e8b57", "#3cb371"],
    };
    var NO_RANGE = ["#666666", "#999999"];

    var mapEl = document.getElementById("river-levels-map");
    if (mapEl && typeof L !== "undefined") {
        var map = L.map(mapEl);
        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
            maxZoom: 19,
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        }).addTo(map);
        var bounds = [];
        stations.forEach(function (s) {
            if (s.lat == null || s.lon == null) return;
            var colours = s.kind === "level" ? (STATUS_COLOURS[s.status] || NO_RANGE) : ["#8e44ad", "#af7ac5"];
            var html = "<strong>" + s.label + "</strong>";
            if (s.river) html += "<br>" + s.river;
            if (s.kind === "level") {
                html += "<br>Level: " + s.latest_display + (s.status ? " (" + s.status.toLowerCase() + ")" : "");
            } else {
                html += "<br>Rainfall: " + s.rain_24h_display + " in 24 hours, " + s.rain_48h_display + " in 48 hours";
            }
            html += "<br>Reading: " + s.latest_time.replace("T", " ") + " UTC";
            L.circleMarker([s.lat, s.lon], { radius: 8, color: colours[0], fillColor: colours[1], fillOpacity: 0.85, weight: 2 })
                .addTo(map).bindPopup(html);
            bounds.push([s.lat, s.lon]);
        });
        if (bounds.length) map.fitBounds(bounds, { padding: [30, 30] });
    }

    if (typeof Chart === "undefined") return;

    function isChelt(s) { return s.river === "River Chelt" || s.river === ""; }
    var levels = stations.filter(function (s) { return s.kind === "level"; });

    function readingsChart(canvasId, group) {
        var canvas = document.getElementById(canvasId);
        if (!canvas || !group.length) return;
        var longest = group.reduce(function (a, b) { return b.readings.length > a.readings.length ? b : a; });
        var labels = longest.readings.map(function (r) { return r[0].slice(5).replace("T", " "); });
        var byTime = function (s) {
            var lookup = {};
            s.readings.forEach(function (r) { lookup[r[0]] = r[1]; });
            return longest.readings.map(function (r) { return lookup[r[0]] == null ? null : lookup[r[0]]; });
        };
        new Chart(canvas, {
            type: "line",
            data: {
                labels: labels,
                datasets: group.map(function (s) {
                    return { label: s.label, data: byTime(s), borderWidth: 2, pointRadius: 0, tension: 0.2, fill: false, spanGaps: true };
                }),
            },
            options: {
                responsive: true,
                interaction: { mode: "index", intersect: false },
                plugins: { legend: { display: true }, tooltip: { callbacks: { label: function (ctx) { return ctx.dataset.label + ": " + ctx.parsed.y.toFixed(2) + " m"; } } } },
                scales: { x: { ticks: { maxTicksLimit: 10 } }, y: { title: { display: true, text: "Level (m)" }, ticks: { callback: function (v) { return v.toFixed(1); } } } },
            },
        });
    }

    readingsChart("river-chelt-chart", levels.filter(isChelt));
    readingsChart("river-brooks-chart", levels.filter(function (s) { return !isChelt(s); }));

    var historyCanvas = document.getElementById("river-history-chart");
    var days = Object.keys(history).sort();
    if (historyCanvas && days.length) {
        var chelt = levels.filter(isChelt);
        new Chart(historyCanvas, {
            type: "line",
            data: {
                labels: days,
                datasets: chelt.map(function (s) {
                    return {
                        label: s.label,
                        data: days.map(function (d) { return history[d][s.reference] ? history[d][s.reference].max : null; }),
                        borderWidth: 2, pointRadius: 0, tension: 0.2, fill: false, spanGaps: true,
                    };
                }),
            },
            options: {
                responsive: true,
                interaction: { mode: "index", intersect: false },
                plugins: { legend: { display: true }, tooltip: { callbacks: { label: function (ctx) { return ctx.dataset.label + ": " + ctx.parsed.y.toFixed(2) + " m"; } } } },
                scales: { x: { ticks: { maxTicksLimit: 10 } }, y: { title: { display: true, text: "Highest level each day (m)" }, ticks: { callback: function (v) { return v.toFixed(1); } } } },
            },
        });
    }
})();
