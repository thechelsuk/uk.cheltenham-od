(function () {
    var el = document.getElementById("deprivation-map");
    var dataEl = document.getElementById("deprivation-data");
    if (!el || !dataEl || typeof L === "undefined") return;

    var areas = [];
    try {
        areas = JSON.parse(dataEl.textContent) || [];
    } catch (e) {
        return;
    }
    if (!areas.length) return;

    var domainEl = document.getElementById("deprivation-domain");

    // The same blues as the crime and broadband maps (shade-1 to shade-5 in
    // themes.css): darker is more deprived. Deciles are paired into fifths.
    var shades = ["#eff3ff", "#c6dbef", "#9ecae1", "#6baed6", "#3182bd", "#08519c"];
    function shadeFor(decile) {
        return shades[5 - Math.floor((decile - 1) / 2)];
    }

    function escapeHtml(text) {
        var div = document.createElement("div");
        div.textContent = text == null ? "" : text;
        return div.innerHTML;
    }

    function label(key) {
        if (!domainEl) return "Overall";
        var option = domainEl.querySelector('option[value="' + key + '"]');
        return option ? option.textContent : key;
    }

    var map = L.map(el, { zoomSnap: 0.25 });
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);

    var group = L.featureGroup().addTo(map);
    var polys = areas.map(function (area) {
        var poly = L.polygon(area.boundary, { color: "#334155", weight: 1, fillOpacity: 0.7 });
        poly.bindTooltip(escapeHtml(area.name), { sticky: true });
        poly.bindPopup(function () {
            var key = domainEl ? domainEl.value : "imd";
            return (
                "<strong>" + escapeHtml(area.name) + "</strong><br>" +
                escapeHtml(area.ward_name) + " ward<br>" +
                "Residents: " + area.population_display + "<br>" +
                "National rank: " + area.rank_display + " (1 = most deprived)<br>" +
                escapeHtml(label(key)) + ": decile " + area.deciles[key] + " of 10"
            );
        });
        poly.area = area;
        poly.addTo(group);
        return poly;
    });

    function render() {
        var key = domainEl ? domainEl.value : "imd";
        polys.forEach(function (poly) {
            poly.setStyle({ fillColor: shadeFor(poly.area.deciles[key]) });
        });
        map.closePopup();
    }

    if (domainEl) domainEl.addEventListener("change", render);
    render();
    map.fitBounds(group.getBounds().pad(0.03));
})();
