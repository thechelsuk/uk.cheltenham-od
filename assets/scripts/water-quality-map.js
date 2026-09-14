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
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution:
            '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);

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
            " readings";
        L.marker([p.lat, p.lon]).addTo(map).bindPopup(html);
        bounds.push([p.lat, p.lon]);
    });

    if (bounds.length) map.fitBounds(bounds, { padding: [30, 30] });
})();
