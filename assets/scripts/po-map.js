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
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution:
            '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);

    var markers = points
        .filter(function (p) {
            return p.lat != null && p.lon != null;
        })
        .map(function (p) {
            var directionsUrl =
                "https://www.google.com/maps/search/?api=1&query=" +
                p.lat +
                "," +
                p.lon;

            var html = "<strong>" + (p.name || "Post Office") + "</strong>";
            if (p.address) html += "<br>" + p.address;
            html +=
                '<br><a href="' +
                directionsUrl +
                '" target="_blank" rel="noopener">Directions ↗</a>';

            return L.marker([p.lat, p.lon]).bindPopup(html);
        });

    if (!markers.length) return;

    var group = L.featureGroup(markers).addTo(map);
    map.fitBounds(group.getBounds().pad(0.15));
})();
