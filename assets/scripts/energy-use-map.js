(function () {
    var el = document.getElementById("energy-map");
    var dataEl = document.getElementById("energy-map-data");
    if (!el || !dataEl || typeof L === "undefined") return;

    var data;
    try {
        data = JSON.parse(dataEl.textContent);
    } catch (e) {
        return;
    }
    if (!data || !data.lsoa || !data.ward) return;

    var levelEl = document.getElementById("energy-map-level");
    var measureEl = document.getElementById("energy-map-measure");
    var caption = document.getElementById("energy-map-caption");
    var legend = document.getElementById("energy-map-legend");

    function escapeHtml(text) {
        var div = document.createElement("div");
        div.textContent = text == null ? "" : text;
        return div.innerHTML;
    }

    // Same six blues as the energy ratings, crime and wards maps. Darker
    // always means more energy used per home.
    var shades = ["#eff3ff", "#c6dbef", "#9ecae1", "#6baed6", "#3182bd", "#08519c"];

    var measures = {
        electricity: { caption: "Average electricity use per home, " + data.small_area_year },
        gas: { caption: "Average gas use per home, " + data.small_area_year },
    };

    function kwh(v) {
        return v.toLocaleString("en-GB") + " kWh";
    }

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
            if (b === 0) label = "Under " + kwh(edges[0]);
            else if (b === shades.length - 1) label = kwh(edges[b - 1]) + " and above";
            else label = kwh(edges[b - 1]) + " to " + kwh(edges[b]);
            html += '<span><i class="tier-swatch shade-' + b + '"></i> ' + label + "</span>";
        }
        legend.innerHTML = html;
    }

    function popupFor(level, area) {
        var html = "<strong>" + escapeHtml(area.name) + "</strong><br>";
        if (level === "lsoa") html += escapeHtml(area.ward_name) + " ward<br>";
        html += "Electricity per home: " + (area.electricity_mean_kwh_display ? area.electricity_mean_kwh_display + " kWh" : "Not published");
        if (area.electricity_median_kwh_display) html += " (median " + area.electricity_median_kwh_display + " kWh)";
        html += "<br>Gas per home: " + (area.gas_mean_kwh_display ? area.gas_mean_kwh_display + " kWh" : "Not published");
        if (area.gas_median_kwh_display) html += " (median " + area.gas_median_kwh_display + " kWh)";
        if (level === "ward" && area.slug) {
            html += '<br><a href="/cheltenham-wards/' + encodeURIComponent(area.slug) + '">View ' + escapeHtml(area.name) + " &rarr;</a>";
        }
        return html;
    }

    var map = L.map(el, { zoomSnap: 0.25 });
    CODMap.tiles(map);

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
        var key = measureEl && measures[measureEl.value] ? measureEl.value : "electricity";
        var edges = data[level][key + "_edges"];

        if (current !== level) {
            if (current) map.removeLayer(layers[current]);
            layers[level].addTo(map);
            current = level;
        }
        layers[level].eachLayer(function (poly) {
            var value = poly.area[key + "_mean_kwh"];
            poly.setStyle(value == null
                ? { fillColor: "#ffffff", fillOpacity: 0.2 }
                : { fillColor: shades[shadeOf(value, edges)], fillOpacity: 0.7 });
        });
        map.closePopup();
        drawLegend(edges);
        if (caption) caption.textContent = measures[key].caption;
    }

    if (levelEl) levelEl.addEventListener("change", render);
    if (measureEl) measureEl.addEventListener("change", render);

    render();
    map.fitBounds(layers.ward.getBounds().pad(0.03));
})();
