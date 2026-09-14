(function () {
    var el = document.getElementById("sewage-map");
    var dataEl = document.getElementById("sewage-data");
    if (!el || !dataEl || typeof L === "undefined") return;

    var overflows = [];
    try {
        overflows = JSON.parse(dataEl.textContent) || [];
    } catch (e) {
        return;
    }
    if (!overflows.length) return;

    var map = L.map(el);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution:
            '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);

    var bounds = [];
    overflows.forEach(function (o) {
        if (o.lat == null || o.lon == null) return;
        var html =
            "<strong>" +
            o.watercourse +
            "</strong><br>" +
            (o.discharging ? "Discharging now" : "Not discharging") +
            (o.latest_event_start
                ? "<br>Last discharge: " + o.latest_event_start
                : "");
        L.circleMarker([o.lat, o.lon], {
            radius: 8,
            color: o.discharging ? "#c0392b" : "#2e8b57",
            fillColor: o.discharging ? "#e74c3c" : "#3cb371",
            fillOpacity: 0.85,
            weight: 2,
        })
            .addTo(map)
            .bindPopup(html);
        bounds.push([o.lat, o.lon]);
    });

    if (bounds.length) map.fitBounds(bounds, { padding: [30, 30] });
})();
