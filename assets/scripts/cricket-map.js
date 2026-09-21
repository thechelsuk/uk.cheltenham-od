(function () {
    var el = document.getElementById("cricket-map");
    var dataEl = document.getElementById("cricket-data");
    if (!el || !dataEl || typeof L === "undefined") return;

    var grounds = [];
    try {
        grounds = JSON.parse(dataEl.textContent) || [];
    } catch (e) {
        return;
    }
    if (!grounds.length) return;

    var map = L.map(el);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution:
            '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);

    var bounds = [];
    grounds.forEach(function (g) {
        if (g.lat == null || g.lon == null) return;
        var directions =
            "https://www.google.com/maps/dir/?api=1&destination=" + g.lat + "," + g.lon;
        var html =
            "<strong>" + g.name + "</strong><br>" + g.address + ", " + g.postcode +
            "<br>" + g.role +
            '<br><a href="' + directions + '" target="_blank" rel="noopener">Directions ↗</a>';
        L.marker([g.lat, g.lon]).addTo(map).bindPopup(html);
        bounds.push([g.lat, g.lon]);
    });

    if (bounds.length) map.fitBounds(bounds, { padding: [40, 40] });
})();
