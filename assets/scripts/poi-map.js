(function () {
    var el = document.getElementById("poi-map");
    var dataEl = document.getElementById("poi-data");
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
            return p.lat != null && p.lng != null;
        })
        .map(function (p) {
            var nameLink = p.wikipedia || p.website;
            var nameHtml = nameLink
                ? '<a href="' +
                  nameLink +
                  '" target="_blank" rel="noopener">' +
                  (p.name || "Point of interest") +
                  "</a>"
                : p.name || "Point of interest";

            var html = "<strong>" + nameHtml + "</strong>";
            if (p.category) html += "<br>" + p.category;
            if (p.postcode) html += "<br>" + p.postcode;
            html += CODMap.directions(p.lat, p.lng);

            return L.marker([p.lat, p.lng]).bindPopup(html);
        });

    if (!markers.length) return;

    var group = L.featureGroup(markers).addTo(map);
    map.fitBounds(group.getBounds().pad(0.15));

    CODMap.linkPins(map, el);
})();
