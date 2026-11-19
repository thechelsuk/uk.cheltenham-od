(function () {
    var el = document.getElementById("permit-zones-map");
    var legendEl = document.getElementById("permit-zones-legend");
    var dataEl = document.getElementById("permit-zones-data");
    if (!el || !dataEl || typeof L === "undefined") return;

    var zones = [];
    try {
        zones = JSON.parse(dataEl.textContent) || [];
    } catch (e) {
        return;
    }
    if (!zones.length) return;

    function escapeHtml(text) {
        var div = document.createElement("div");
        div.textContent = text == null ? "" : text;
        return div.innerHTML;
    }

    // Only http and https links from the data go into a popup.
    function safeUrl(url) {
        try {
            var parsed = new URL(url, window.location.href);
            return parsed.protocol === "https:" || parsed.protocol === "http:" ? parsed.href : null;
        } catch (e) {
            return null;
        }
    }

    function legendItem(color, label) {
        var item = document.createElement("span");
        var swatch = document.createElement("span");
        swatch.className = "catchment-swatch";
        swatch.style.setProperty("--swatch", color);
        item.appendChild(swatch);
        item.appendChild(document.createTextNode(label));
        return item;
    }

    // Golden-angle hue rotation, as on the school catchment map, so
    // neighbouring zones get clearly different colours.
    function colorForIndex(i) {
        var hue = (i * 137.508) % 360;
        return "hsl(" + hue.toFixed(0) + ", 62%, 42%)";
    }

    function zoneLabel(z) {
        return "Zone " + z.code + (z.name ? ": " + z.name : "");
    }

    var map = L.map(el);
    CODMap.tiles(map);

    var group = [];
    if (legendEl) legendEl.textContent = "";

    zones.forEach(function (z, i) {
        var color = colorForIndex(i);
        (z.lines || []).forEach(function (line) {
            var polyline = L.polyline(line.geometry, {
                color: color,
                weight: 5,
                opacity: 0.85,
                dashArray: line.part ? "6 6" : null,
            }).addTo(map);
            var mapUrl = safeUrl(z.map_url);
            polyline.bindPopup(
                "<strong>" +
                    escapeHtml(line.street) +
                    "</strong><br>" +
                    escapeHtml(zoneLabel(z)) +
                    (line.part ? "<br>Part of street only" : "") +
                    (mapUrl
                        ? '<br><a href="' +
                          escapeHtml(mapUrl) +
                          '" target="_blank" rel="noopener">Council zone map ↗</a>'
                        : "")
            );
            group.push(polyline);
        });

        if (legendEl) {
            legendEl.appendChild(legendItem(color, zoneLabel(z)));
            legendEl.appendChild(document.createTextNode(" "));
        }
    });

    if (group.length) map.fitBounds(L.featureGroup(group).getBounds().pad(0.05));

    CODMap.linkPins(map, el);
})();
