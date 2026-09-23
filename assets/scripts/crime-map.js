(function () {
    var el = document.getElementById("crime-map");
    var dataEl = document.getElementById("crime-map-data");
    if (!el || !dataEl || typeof L === "undefined") return;

    var data;
    try {
        data = JSON.parse(dataEl.textContent);
    } catch (e) {
        return;
    }
    if (!data || !data.windows || !data.windows.length || !data.lsoa || !data.ward) return;

    var levelEl = document.getElementById("crime-map-level");
    var windowEl = document.getElementById("crime-map-window");
    var windowLabel = document.getElementById("crime-map-window-label");
    var legend = document.getElementById("crime-map-legend");

    function escapeHtml(text) {
        var div = document.createElement("div");
        div.textContent = text == null ? "" : text;
        return div.innerHTML;
    }

    function thousands(n) {
        return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
    }

    // Same six blues as the broadband and wards maps. Band edges are fixed
    // across every 12-month window so the colours stay comparable as the
    // slider moves.
    var shades = ["#eff3ff", "#c6dbef", "#9ecae1", "#6baed6", "#3182bd", "#08519c"];

    function shadeOf(value, edges) {
        var band = 0;
        while (band < edges.length && value >= edges[band]) band++;
        return band;
    }

    function drawLegend(edges) {
        if (!legend) return;
        var html = "";
        for (var b = 0; b < shades.length; b++) {
            var label;
            if (b === 0) label = "Under " + edges[0];
            else if (b === shades.length - 1) label = edges[b - 1] + "+";
            else label = edges[b - 1] + " to " + edges[b];
            html += '<span><i class="tier-swatch shade-' + b + '"></i> ' + label + "</span>";
        }
        legend.innerHTML = html;
    }

    var map = L.map(el, { zoomSnap: 0.25 });
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);

    var layers = {};
    ["lsoa", "ward"].forEach(function (level) {
        var group = L.featureGroup();
        data[level].areas.forEach(function (area) {
            var poly = L.polygon(area.boundary, { color: "#334155", weight: level === "ward" ? 2 : 1, fillOpacity: 0.7 });
            poly.bindTooltip(escapeHtml(area.name), { sticky: true });
            poly.bindPopup(function () {
                return popupFor(level, area, selected);
            });
            poly.area = area;
            poly.addTo(group);
        });
        layers[level] = group;
    });

    function popupFor(level, area, i) {
        var w = data.windows[i];
        var html = "<strong>" + escapeHtml(area.name) + "</strong><br>";
        if (level === "lsoa") html += escapeHtml(area.ward_name) + " ward<br>";
        html +=
            w.first_month + " to " + w.last_month + "<br>" +
            "Crimes: " + thousands(area.crimes[i]) + "<br>" +
            "Residents: " + thousands(area.residents[i]) + "<br>" +
            "Per 1,000 residents: " + area.rate[i].toFixed(1);
        if (level === "ward" && area.slug) {
            html += '<br><a href="/cheltenham-wards/' + encodeURIComponent(area.slug) + '">View ' + escapeHtml(area.name) + " &rarr;</a>";
        }
        return html;
    }

    var current = null;
    var selected = data.windows.length - 1;

    function render() {
        var level = levelEl && levelEl.value === "ward" ? "ward" : "lsoa";
        var i = windowEl ? parseInt(windowEl.value, 10) : data.windows.length - 1;
        if (isNaN(i) || i < 0 || i >= data.windows.length) i = data.windows.length - 1;
        var edges = data[level].bands;

        if (current !== level) {
            if (current) map.removeLayer(layers[current]);
            layers[level].addTo(map);
            current = level;
        }
        layers[level].eachLayer(function (poly) {
            poly.setStyle({ fillColor: shades[shadeOf(poly.area.rate[i], edges)] });
        });
        selected = i;
        map.closePopup();

        drawLegend(edges);
        if (windowLabel) {
            windowLabel.textContent = data.windows[i].first_month + " to " + data.windows[i].last_month;
        }
    }

    if (levelEl) levelEl.addEventListener("change", render);
    if (windowEl) windowEl.addEventListener("input", render);

    render();
    map.fitBounds(layers.lsoa.getBounds().pad(0.03));
})();
