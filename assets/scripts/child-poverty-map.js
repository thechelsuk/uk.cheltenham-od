(function () {
    var el = document.getElementById("child-poverty-map");
    var dataEl = document.getElementById("child-poverty-map-data");
    var measureEl = document.getElementById("child-poverty-measure");
    if (!el || !dataEl || !measureEl || typeof L === "undefined") return;

    var wards = [];
    try {
        wards = JSON.parse(dataEl.textContent) || [];
    } catch (e) {
        return;
    }
    if (!wards.length) return;

    var shades = ["#eff3ff", "#c6dbef", "#9ecae1", "#6baed6", "#3182bd"];

    function escapeHtml(text) {
        var div = document.createElement("div");
        div.textContent = text == null ? "" : text;
        return div.innerHTML;
    }

    function shadeFor(percentage) {
        if (percentage < 10) return shades[0];
        if (percentage < 20) return shades[1];
        if (percentage < 30) return shades[2];
        if (percentage < 40) return shades[3];
        return shades[4];
    }

    var map = L.map(el, { zoomSnap: 0.25 });
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);

    var group = L.featureGroup().addTo(map);
    var polygons = wards.map(function (ward) {
        var polygon = L.polygon(ward.boundary, {
            color: "#334155",
            weight: 2,
            fillOpacity: 0.7,
        });
        polygon.bindTooltip(escapeHtml(ward.name), { sticky: true });
        polygon.bindPopup(function () {
            var value = ward.values[measureEl.value];
            return (
                "<strong>" + escapeHtml(ward.name) + "</strong><br>" +
                escapeHtml(measureEl.options[measureEl.selectedIndex].text) + ": " +
                escapeHtml(value.percentage_display) + "<br>" +
                escapeHtml(value.children_display) + " children<br>" +
                '<a href="/cheltenham-wards/' + encodeURIComponent(ward.slug) + '">View ward profile &rarr;</a>'
            );
        });
        polygon.ward = ward;
        polygon.addTo(group);
        return polygon;
    });

    function render() {
        polygons.forEach(function (polygon) {
            var value = polygon.ward.values[measureEl.value].percentage;
            polygon.setStyle({
                fillColor: value == null ? "#d1d5db" : shadeFor(value),
            });
        });
        map.closePopup();
    }

    measureEl.addEventListener("change", render);
    render();
    map.fitBounds(group.getBounds().pad(0.03));
})();
