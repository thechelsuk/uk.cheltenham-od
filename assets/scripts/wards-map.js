(function () {
    var el = document.getElementById("wards-map");
    var dataEl = document.getElementById("wards-map-data");
    if (!el || !dataEl || typeof L === "undefined") return;

    var wards = [];
    try {
        wards = JSON.parse(dataEl.textContent) || [];
    } catch (e) {
        return;
    }
    if (!wards.length) return;

    function escapeHtml(text) {
        var div = document.createElement("div");
        div.textContent = text == null ? "" : text;
        return div.innerHTML;
    }

    function short(n) {
        return "£" + Math.round(n / 1000) + "k";
    }

    // Same six blues as the broadband map, in equal-sized bands of wards.
    var shades = ["#eff3ff", "#c6dbef", "#9ecae1", "#6baed6", "#3182bd", "#08519c"];
    var sorted = wards.map(function (w) { return w.median; }).sort(function (a, b) { return a - b; });
    var edges = [];
    for (var i = 1; i < shades.length; i++) {
        edges.push(sorted[Math.min(sorted.length - 1, Math.round((i * sorted.length) / shades.length))]);
    }

    function shadeOf(value) {
        var band = 0;
        while (band < edges.length && value >= edges[band]) band++;
        return band;
    }

    var legend = document.getElementById("wards-legend");
    if (legend) {
        var html = "";
        for (var b = 0; b < shades.length; b++) {
            var from = b === 0 ? sorted[0] : edges[b - 1];
            var to = b === shades.length - 1 ? sorted[sorted.length - 1] : edges[b];
            html += '<span><i class="tier-swatch shade-' + b + '"></i> ' + short(from) + " to " + short(to) + "</span>";
        }
        legend.innerHTML = html;
    }

    var map = L.map(el, { zoomSnap: 0.25 });
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);

    var group = L.featureGroup().addTo(map);
    wards.forEach(function (w) {
        var poly = L.polygon(w.boundary, {
            color: "#334155",
            weight: 2,
            fillColor: shades[shadeOf(w.median)],
            fillOpacity: 0.7,
        });
        var popup =
            "<strong>" + escapeHtml(w.name) + "</strong><br>" +
            "Median sale price: " + escapeHtml(w.median_display) + "<br>" +
            "Crimes, 12 months: " + w.crime_total + "<br>" +
            "Gigabit broadband: " + w.gigabit_pct + "%<br>" +
            '<a href="/cheltenham-wards/' + encodeURIComponent(w.slug) + '">View ' + escapeHtml(w.name) + " &rarr;</a>";
        poly.bindPopup(popup);
        poly.bindTooltip(escapeHtml(w.name), { sticky: true });
        poly.addTo(group);
    });

    map.fitBounds(group.getBounds().pad(0.03));
})();
