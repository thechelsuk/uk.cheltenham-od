(function () {
    var el = document.getElementById("po-map");
    var dataEl = document.getElementById("po-data");
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

    var markers = points
        .filter(function (p) {
            return p.lat != null && p.lon != null;
        })
        .map(function (p) {
            var html = "<strong>" + (p.name || "Post Office") + "</strong>";
            if (p.address) html += "<br>" + p.address;
            html += CODMap.directions(p.lat, p.lon);

            return L.marker([p.lat, p.lon]).bindPopup(html);
        });

    if (!markers.length) return;

    var group = L.featureGroup(markers).addTo(map);
    map.fitBounds(group.getBounds().pad(0.15));

    CODMap.linkPins(map, el);
})();
