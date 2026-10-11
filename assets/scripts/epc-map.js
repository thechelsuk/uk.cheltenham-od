(function () {
    var el = document.getElementById("epc-map");
    var dataEl = document.getElementById("epc-map-data");
    if (!el || !dataEl || typeof L === "undefined") return;

    var data;
    try {
        data = JSON.parse(dataEl.textContent);
    } catch (e) {
        return;
    }
    if (!data || !data.lsoa || !data.ward) return;

    var levelEl = document.getElementById("epc-map-level");
    var measureEl = document.getElementById("epc-map-measure");
    var caption = document.getElementById("epc-map-caption");
    var legend = document.getElementById("epc-map-legend");
    var bands = "ABCDEFG";

    function escapeHtml(text) {
        var div = document.createElement("div");
        div.textContent = text == null ? "" : text;
        return div.innerHTML;
    }

    // An average score as its letter: G is 1 up to A at 7, halves round up.
    function bandFor(score) {
        return bands.charAt(7 - Math.min(7, Math.max(1, Math.floor(score + 0.5))));
    }

    // Same six blues as the crime, broadband and wards maps; darker is better
    // on both measures.
    var shades = ["#eff3ff", "#c6dbef", "#9ecae1", "#6baed6", "#3182bd", "#08519c"];

    var measures = {
        score: {
            caption: "Average rating, counting G as 1 up to A as 7",
            value: function (area) { return area.average_score; },
            edges: function (level) { return data[level].score_edges; },
            label: function (v) { return bandFor(v) + " (" + v.toFixed(2) + ")"; },
        },
        share: {
            caption: "Share of homes rated C or better",
            value: function (area) { return area.c_or_better_pct; },
            edges: function (level) { return data[level].share_edges; },
            label: function (v) { return v + "%"; },
        },
    };

    function shadeOf(value, edges) {
        var band = 0;
        while (band < edges.length && value >= edges[band]) band++;
        return band;
    }

    function drawLegend(measure, edges) {
        if (!legend) return;
        var html = "";
        for (var b = 0; b < shades.length; b++) {
            var label;
            if (b === 0) label = "Under " + measure.label(edges[0]);
            else if (b === shades.length - 1) label = measure.label(edges[b - 1]) + " and above";
            else label = measure.label(edges[b - 1]) + " to " + measure.label(edges[b]);
            html += '<span><i class="tier-swatch shade-' + b + '"></i> ' + label + "</span>";
        }
        legend.innerHTML = html;
    }

    function popupFor(level, area) {
        var html = "<strong>" + escapeHtml(area.name) + "</strong><br>";
        if (level === "lsoa") html += escapeHtml(area.ward_name) + " ward<br>";
        if (!area.homes) return html + "No rated homes";
        html +=
            "Homes with a certificate: " + area.homes_display + "<br>" +
            "Average rating: " + area.average_band + " (" + area.average_score.toFixed(2) + ")<br>" +
            "Rated C or better: " + area.c_or_better_pct + "%<br>";
        for (var i = 0; i < bands.length; i++) {
            var b = bands.charAt(i);
            html += b + ": " + area.counts_display[b] + (i < bands.length - 1 ? " · " : "");
        }
        if (level === "ward" && area.slug) {
            html += '<br><a href="/cheltenham-wards/' + encodeURIComponent(area.slug) + '">View ' + escapeHtml(area.name) + " &rarr;</a>";
        }
        return html;
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
            poly.bindPopup(popupFor(level, area));
            poly.area = area;
            poly.addTo(group);
        });
        layers[level] = group;
    });

    var current = null;

    function render() {
        var level = levelEl && levelEl.value === "lsoa" ? "lsoa" : "ward";
        var measure = measures[measureEl && measureEl.value === "share" ? "share" : "score"];
        var edges = measure.edges(level);

        if (current !== level) {
            if (current) map.removeLayer(layers[current]);
            layers[level].addTo(map);
            current = level;
        }
        layers[level].eachLayer(function (poly) {
            var value = measure.value(poly.area);
            poly.setStyle(value == null
                ? { fillColor: "#ffffff", fillOpacity: 0.2 }
                : { fillColor: shades[shadeOf(value, edges)], fillOpacity: 0.7 });
        });
        map.closePopup();
        drawLegend(measure, edges);
        if (caption) caption.textContent = measure.caption;
    }

    if (levelEl) levelEl.addEventListener("change", render);
    if (measureEl) measureEl.addEventListener("change", render);

    render();
    map.fitBounds(layers.ward.getBounds().pad(0.03));
})();
