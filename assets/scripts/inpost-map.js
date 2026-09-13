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
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution:
            '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);

    var markers = lockers
        .filter(function (l) {
            return l.lat != null && l.lon != null;
        })
        .map(function (l) {
            var directionsUrl =
                "https://www.google.com/maps/search/?api=1&query=" + l.lat + "," + l.lon;

            var html = "<strong>" + (l.name || "InPost Locker") + "</strong>";
            if (l.street) html += "<br>" + l.street;
            if (l.postcode) html += " " + l.postcode;
            if (l.is_247) html += "<br>Open 24/7";
            html +=
                '<br><a href="' +
                directionsUrl +
                '" target="_blank" rel="noopener">Directions ↗</a>';

            return L.marker([l.lat, l.lon]).bindPopup(html);
        });

    if (!markers.length) return;

    var group = L.featureGroup(markers).addTo(map);
    map.fitBounds(group.getBounds().pad(0.15));
})();
