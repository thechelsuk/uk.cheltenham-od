(function () {
    var el = document.getElementById("foodbank-map");
    var dataEl = document.getElementById("foodbank-data");
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


    function escapeHtml(text) {
        var div = document.createElement("div");
        div.textContent = text == null ? "" : String(text);
        return div.innerHTML;
    }

    var bounds = [];
    points.forEach(function (p) {
        if (p.lat == null || p.lon == null) return;

        var html = "<strong>" + escapeHtml(p.name) + "</strong>";
        if (p.label) html += "<br>" + escapeHtml(p.label);
        if (p.href) html += '<br><a href="' + escapeHtml(p.href) + '">View details</a>';

        html += CODMap.directions(p.lat, p.lon);

        // Food banks get the standard pin; donation points get the accent pin.
        var marker = p.kind === "donation"
            ? L.marker([p.lat, p.lon], { icon: CODMap.accentIcon(), zIndexOffset: 500 })
            : L.marker([p.lat, p.lon]);
        marker.addTo(map).bindPopup(html);
        bounds.push([p.lat, p.lon]);
    });

    if (bounds.length === 1) map.setView(bounds[0], 15);
    else map.fitBounds(bounds, { padding: [30, 30], maxZoom: 15 });

    CODMap.linkPins(map, el);
})();
