(function () {
    var el = document.getElementById("inpost-map");
    var dataEl = document.getElementById("inpost-data");
    if (!el || !dataEl || typeof L === "undefined") return;

    var lockers = [];
    try {
        lockers = JSON.parse(dataEl.textContent) || [];
    } catch (e) {
        return;
    }
    if (!lockers.length) return;

    var map = L.map(el);
    CODMap.tiles(map);

    var markers = lockers
        .filter(function (l) {
            return l.lat != null && l.lon != null;
        })
        .map(function (l) {
            var html = "<strong>" + (l.name || "InPost Locker") + "</strong>";
            if (l.street) html += "<br>" + l.street;
            if (l.postcode) html += " " + l.postcode;
            if (l.is_247) html += "<br>Open 24/7";
            html += CODMap.directions(l.lat, l.lon);

            return L.marker([l.lat, l.lon]).bindPopup(html);
        });

    if (!markers.length) return;

    var group = L.featureGroup(markers).addTo(map);
    map.fitBounds(group.getBounds().pad(0.15));

    CODMap.linkPins(map, el);
})();
