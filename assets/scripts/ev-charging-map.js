(function () {
    var el = document.getElementById("ev-charging-data");
    var mapEl = document.getElementById("ev-map");
    if (!el || !mapEl || typeof L === "undefined") return;

    var stations = JSON.parse(el.textContent);
    var map = L.map("ev-map");

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution: "© OpenStreetMap contributors",
    }).addTo(map);

    var markers = [];
    stations.forEach(function (s) {
        if (s.latitude == null || s.longitude == null) return;

        var conns = (s.connections || [])
            .map(function (c) {
                return (
                    (c.quantity ? c.quantity + "× " : "") +
                    (c.type || "Unknown") +
                    (c.power_kw ? " (" + c.power_kw + " kW)" : "")
                );
            })
            .join("<br>");

        var html = "<strong>" + (s.name || "Charging point") + "</strong>";
        if (s.operator) html += "<br>" + s.operator;
        var addr = [s.address, s.postcode].filter(Boolean).join(", ");
        if (addr) html += "<br>" + addr;
        if (conns) html += "<br>" + conns;
        html +=
            '<br><a href="' +
            s.google_maps_url +
            '" target="_blank" rel="noopener">Directions ↗</a>';

        var m = L.marker([s.latitude, s.longitude]).bindPopup(html);
        m.addTo(map);
        markers.push(m);
    });

    if (markers.length) {
        map.fitBounds(L.featureGroup(markers).getBounds().pad(0.1));
    } else {
        map.setView([51.9, -2.08], 13);
    }
})();
