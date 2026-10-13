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
    CODMap.tiles(map);

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
                : "") +
            CODMap.directions(o.lat, o.lon);
        // Discharging overflows get the accent pin.
        var marker = o.discharging
            ? L.marker([o.lat, o.lon], { icon: CODMap.accentIcon(), zIndexOffset: 500 })
            : L.marker([o.lat, o.lon]);
        marker.addTo(map).bindPopup(html);
        bounds.push([o.lat, o.lon]);
    });

    if (bounds.length) map.fitBounds(bounds, { padding: [30, 30] });

    CODMap.linkPins(map, el);
})();
