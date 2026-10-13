(function () {
    var el = document.getElementById("dentists-map");
    var dataEl = document.getElementById("dentists-data");
    if (!el || !dataEl || typeof L === "undefined") return;

    var practices = [];
    try {
        practices = JSON.parse(dataEl.textContent) || [];
    } catch (e) {
        return;
    }
    if (!practices.length) return;

    var map = L.map(el);
    CODMap.tiles(map);

    var bounds = [];
    practices.forEach(function (p) {
        if (p.lat == null || p.lon == null) return;
        var html = "<strong>" + p.name + "</strong><br>" + p.address + (p.postcode ? ", " + p.postcode : "");
        html += CODMap.directions(p.lat, p.lon);
        L.marker([p.lat, p.lon]).addTo(map).bindPopup(html);
        bounds.push([p.lat, p.lon]);
    });

    if (bounds.length) map.fitBounds(bounds, { padding: [30, 30] });

    CODMap.linkPins(map, el);
})();
