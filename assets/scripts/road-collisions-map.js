(function () {
    var el = document.getElementById("road-collisions-map");
    var dataEl = document.getElementById("road-collisions-map-data");
    if (!el || !dataEl || typeof L === "undefined") return;

    var collisions = [];
    try {
        collisions = JSON.parse(dataEl.textContent) || [];
    } catch (e) {
        return;
    }
    if (!collisions.length) return;

    function escapeHtml(text) {
        var div = document.createElement("div");
        div.textContent = text == null ? "" : text;
        return div.innerHTML;
    }

    var map = L.map(el);
    CODMap.tiles(map);

    var bounds = [];
    collisions.forEach(function (c) {
        var html =
            "<strong>" + escapeHtml(c.severity) + " collision</strong><br>" +
            escapeHtml(c.date) + " " + escapeHtml(c.time) + "<br>" +
            escapeHtml(c.road) + (c.speed_limit ? ", " + c.speed_limit + " mph" : "") + "<br>" +
            "Casualties: " + escapeHtml(c.casualties_summary) + "<br>" +
            "Vehicles: " + escapeHtml(c.vehicles) +
            CODMap.directions(c.lat, c.lon);
        L.marker([c.lat, c.lon]).addTo(map).bindPopup(html);
        bounds.push([c.lat, c.lon]);
    });

    map.fitBounds(bounds, { padding: [30, 30] });

    CODMap.linkPins(map, el);
})();
