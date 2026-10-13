(function () {
    var el = document.getElementById("water-quality-map");
    var dataEl = document.getElementById("water-quality-data");
    if (!el || !dataEl || typeof L === "undefined") return;

    var points = [];
    try {
        points = JSON.parse(dataEl.textContent) || [];
    } catch (e) {
        return;
    }
    if (!points.length) return;

    var map = L.map(el);
    CODMap.tiles(map);

    var bounds = [];
    points.forEach(function (p) {
        if (p.lat == null || p.lon == null) return;
        var html =
            "<strong>" +
            p.name +
            "</strong><br>Last sampled: " +
            p.latest_date +
            "<br>" +
            p.readings.length +
            " readings" +
            CODMap.directions(p.lat, p.lon);
        L.marker([p.lat, p.lon]).addTo(map).bindPopup(html);
        bounds.push([p.lat, p.lon]);
    });

    if (bounds.length) map.fitBounds(bounds, { padding: [30, 30] });

    CODMap.linkPins(map, el);
})();
