(function () {
    var el = document.getElementById("toilet-map");
    var dataEl = document.getElementById("toilet-data");
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
            return p.latitude != null && p.longitude != null;
        })
        .map(function (p) {
            var directionsUrl =
                p.maps_url ||
                "https://www.google.com/maps/search/?api=1&query=" +
                    p.latitude +
                    "," +
                    p.longitude;

            var features = [];
            if (p.accessible) features.push("Wheelchair accessible");
            if (p.all_gender) features.push("All gender");
            if (p.baby_change) features.push("Baby changing");
            if (p.men && p.women) features.push("Male and female");
            else if (p.men) features.push("Male only");
            else if (p.women) features.push("Female only");
            if (p.urinal_only) features.push("Urinal only");
            if (p.radar_key) features.push("RADAR key required");
            if (p.no_payment) features.push("Free to use");
            else if (p.payment_details)
                features.push("Charge: " + p.payment_details);

            var html = "<strong>" + (p.name || "Public toilet") + "</strong>";
            if (features.length) html += "<br>" + features.join("<br>");
            if (p.opening_hours_summary)
                html += "<br>" + p.opening_hours_summary;
            html +=
                '<br><a href="' +
                directionsUrl +
                '" target="_blank" rel="noopener">Directions ↗</a>';

            return L.marker([p.latitude, p.longitude]).bindPopup(html);
        });

    if (!markers.length) return;

    var group = L.featureGroup(markers).addTo(map);
    map.fitBounds(group.getBounds().pad(0.15));
})();
