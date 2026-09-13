(function () {
    var el = document.getElementById("broadband-map");
    var dataEl = document.getElementById("broadband-map-data");
    if (!el || !dataEl || typeof L === "undefined") return;

    var geo;
    try {
        geo = JSON.parse(dataEl.textContent);
    } catch (e) {
        return;
    }
    if (!geo || !geo.features || !geo.features.length) return;

    var map = L.map(el);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution:
            '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);

    var layer = L.geoJSON(geo, {
        style: function (feature) {
            return {
                color: "#555",
                weight: 1,
                fillColor: feature.properties["marker-color"] || "#cccccc",
                fillOpacity: 0.65,
            };
        },
        onEachFeature: function (feature, lyr) {
            var p = feature.properties;
            var html =
                "<strong>" +
                (p.name || "Ward") +
                "</strong>" +
                "<br>" +
                (p.tier_label || "") +
                "<br>" +
                (p.unit_count || 0) +
                " postcodes" +
                "<br>Superfast (30+): " +
                p.sfbb_pct +
                "%" +
                "<br>Ultrafast (100+): " +
                p.ufbb100_pct +
                "%" +
                "<br>Ultrafast (300+): " +
                p.ufbb300_pct +
                "%" +
                "<br>Gigabit: " +
                p.gigabit_pct +
                "%";
            lyr.bindPopup(html);
        },
    }).addTo(map);

    map.fitBounds(layer.getBounds().pad(0.05));
})();
