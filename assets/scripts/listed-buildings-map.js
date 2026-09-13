(function () {
    var el = document.getElementById("listed-buildings-map");
    var dataEl = document.getElementById("listed-buildings-data");
    var areasEl = document.getElementById("listed-buildings-areas-data");
    if (!el || !dataEl || typeof L === "undefined") return;

    var buildings = [];
    try {
        buildings = JSON.parse(dataEl.textContent) || [];
    } catch (e) {
        return;
    }

    var areas = [];
    if (areasEl) {
        try {
            areas = JSON.parse(areasEl.textContent) || [];
        } catch (e) {
            areas = [];
        }
    }

    if (!buildings.length && !areas.length) return;

    var map = L.map(el);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution:
            '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);

    var gradeColours = { I: "#b30000", "II*": "#e07b00", II: "#3366cc" };

    var markers = [];
    buildings
        .filter(function (b) {
            return b.lat != null && b.lon != null;
        })
        .forEach(function (b) {
            var html = "<strong>" + b.name + "</strong><br>Grade " + b.grade;
            if (b.hyperlink) {
                html += '<br><a href="' + b.hyperlink + '" target="_blank" rel="noopener">View listing &#8599;</a>';
            }
            var marker = L.circleMarker([b.lat, b.lon], {
                radius: 5,
                color: gradeColours[b.grade] || "#3366cc",
                fillColor: gradeColours[b.grade] || "#3366cc",
                fillOpacity: 0.8,
                weight: 1,
            }).bindPopup(html);
            marker.addTo(map);
            markers.push(marker);
        });

    var areaLayer = L.geoJSON(
        areas.filter(function (a) {
            return a.geometry;
        }).map(function (a) {
            return { type: "Feature", geometry: a.geometry, properties: a };
        }),
        {
            style: { color: "#2e7d32", weight: 2, fillOpacity: 0.15 },
            onEachFeature: function (feature, layer) {
                var props = feature.properties;
                var html = "<strong>" + props.name + "</strong>";
                if (props.hyperlink) {
                    html += '<br><a href="' + props.hyperlink + '" target="_blank" rel="noopener">View listing &#8599;</a>';
                }
                layer.bindPopup(html);
            },
        }
    ).addTo(map);

    // The container can still be mid-layout when this script runs (script
    // tags execute synchronously as the page streams in), which leaves
    // Leaflet's cached size stale and fitBounds zoomed out incorrectly.
    map.invalidateSize();

    var group = L.featureGroup(markers.concat([areaLayer]));
    if (group.getLayers().length) {
        map.fitBounds(group.getBounds().pad(0.1));
    } else {
        map.setView([51.9, -2.08], 13);
    }
})();
