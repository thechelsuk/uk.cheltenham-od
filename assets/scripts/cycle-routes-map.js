(function () {
    var el = document.getElementById("cycle-routes-map");
    var dataEl = document.getElementById("cycle-routes-data");
    var poiEl = document.getElementById("cycle-routes-poi-data");
    if (!el || !dataEl || typeof L === "undefined") return;

    var segments = [];
    try {
        segments = JSON.parse(dataEl.textContent) || [];
    } catch (e) {
        return;
    }

    var spots = [];
    try {
        spots = poiEl ? JSON.parse(poiEl.textContent) || [] : [];
    } catch (e) {
        spots = [];
    }

    if (!segments.length && !spots.length) return;

    var map = L.map(el);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);

    var COLORS = { track: "#2f6b4f", lane: "#b5561f", named: "#1d4e89" };

    var bounds = [];
    segments.forEach(function (seg) {
        if (!seg.geometry || seg.geometry.length < 2) return;

        var named = !!seg.route_ref;
        var line = L.polyline(seg.geometry, {
            color: named ? COLORS.named : COLORS[seg.kind] || COLORS.track,
            weight: named ? 4 : 2,
            opacity: named ? 0.9 : 0.7,
        }).addTo(map);

        var label = seg.route_ref || seg.name || (seg.kind === "lane" ? "On-road cycle lane" : "Cycle track");
        var html = "<strong>" + label + "</strong>";
        if (seg.surface) html += "<br>Surface: " + seg.surface;
        if (seg.lit) html += "<br>Lit";
        line.bindPopup(html);

        bounds = bounds.concat(seg.geometry);
    });

    spots.forEach(function (spot) {
        if (spot.lat == null || spot.lon == null) return;
        var html = "<strong>" + spot.name + "</strong><br>" + spot.kind;
        if (spot.address) html += "<br>" + spot.address;
        L.marker([spot.lat, spot.lon]).addTo(map).bindPopup(html);
        bounds.push([spot.lat, spot.lon]);
    });

    if (bounds.length) map.fitBounds(bounds, { padding: [30, 30] });
})();
