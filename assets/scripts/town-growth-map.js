(function () {
    var el = document.getElementById("town-growth-map");
    var dataEl = document.getElementById("town-growth-data");
    if (!el || !dataEl || typeof L === "undefined") return;

    var data;
    try {
        data = JSON.parse(dataEl.textContent);
    } catch (e) {
        return;
    }
    if (!data || !data.years || !data.bands || !data.outlines) return;

    var yearEl = document.getElementById("town-growth-year");
    var yearLabel = document.getElementById("town-growth-year-label");
    var legend = document.getElementById("town-growth-legend");
    var last = data.years.length - 1;

    function escapeHtml(text) {
        var div = document.createElement("div");
        div.textContent = text == null ? "" : text;
        return div.innerHTML;
    }

    // One blue per five-year period: the oldest land darkest, the newest palest.
    var shades = ["#08306b", "#08519c", "#2171b5", "#4292c6", "#6baed6", "#9ecae1", "#b3d3e8", "#c6dbef", "#dbe9f6", "#eff3ff"];

    var map = L.map(el, { zoomSnap: 0.25 });
    CODMap.tiles(map);

    var districts = L.geoJSON(data.outlines, {
        style: { color: "#334155", weight: 1.5, dashArray: "4 4", fill: false },
        interactive: false,
    }).addTo(map);
    districts.eachLayer(function (layer) {
        layer.bindTooltip(escapeHtml(layer.feature.properties.name), {
            permanent: true,
            direction: "center",
        });
    });

    // One layer per period, added and removed as the slider moves.
    var periods = data.years.map(function (year, k) {
        return L.geoJSON(
            {
                type: "FeatureCollection",
                features: data.bands.features.filter(function (f) {
                    return f.properties.band === k;
                }),
            },
            {
                style: { color: "#334155", weight: 0.3, fillColor: shades[k], fillOpacity: 0.75 },
                onEachFeature: function (feature, layer) {
                    var p = feature.properties;
                    layer.bindPopup(
                        "<strong>" + escapeHtml(p.district) + "</strong><br>" +
                        "First built up: " + escapeHtml(p.label),
                    );
                },
            },
        );
    });

    function drawLegend(n) {
        if (!legend) return;
        var html = "";
        for (var k = 0; k <= n; k++) {
            var newest = k === n && n > 0;
            html +=
                '<span><i class="tier-swatch' + (newest ? " tier-swatch-newest" : "") + '" style="--swatch: ' + shades[k] + '"></i> ' +
                escapeHtml(data.periods[k]) + (newest ? " (newest, outlined)" : "") + "</span>";
        }
        legend.innerHTML = html;
    }

    function render() {
        var n = yearEl ? parseInt(yearEl.value, 10) : last;
        if (isNaN(n) || n < 0 || n > last) n = last;
        periods.forEach(function (layer, k) {
            if (k <= n) {
                if (!map.hasLayer(layer)) layer.addTo(map);
                // The newest period gets a heavy outline, so new land stands out without relying on colour.
                var newest = k === n && n > 0;
                layer.setStyle({ color: newest ? "#0f172a" : "#334155", weight: newest ? 2.5 : 0.3 });
            } else if (map.hasLayer(layer)) {
                map.removeLayer(layer);
            }
        });
        // Keep the newest outline on top of the older shading.
        if (n > 0) periods[n].bringToFront();
        map.closePopup();
        drawLegend(n);
        if (yearLabel) yearLabel.textContent = data.years[n];
    }

    if (yearEl) yearEl.addEventListener("input", render);

    render();
    map.fitBounds(districts.getBounds().pad(0.02));
})();
