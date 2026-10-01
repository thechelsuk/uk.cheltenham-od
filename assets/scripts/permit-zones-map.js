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
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution:
            '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);

    var group = [];
    var legendHtml = "";

    zones.forEach(function (z, i) {
        var color = colorForIndex(i);
        (z.lines || []).forEach(function (line) {
            var polyline = L.polyline(line.geometry, {
                color: color,
                weight: 5,
                opacity: 0.85,
                dashArray: line.part ? "6 6" : null,
            }).addTo(map);
            polyline.bindPopup(
                "<strong>" +
                    line.street +
                    "</strong><br>" +
                    zoneLabel(z) +
                    (line.part ? "<br>Part of street only" : "") +
                    '<br><a href="' +
                    z.map_url +
                    '" target="_blank" rel="noopener">Council zone map ↗</a>'
            );
            group.push(polyline);
        });

        legendHtml +=
            '<span><span class="catchment-swatch" style="background:' +
            color +
            '"></span>' +
            zoneLabel(z) +
            "</span> ";
    });

    if (legendEl) legendEl.innerHTML = legendHtml;

    if (group.length) map.fitBounds(L.featureGroup(group).getBounds().pad(0.05));
})();
