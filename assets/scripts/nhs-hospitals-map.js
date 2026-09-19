(function () {
    var el = document.getElementById("nhs-hospitals-map");
    var dataEl = document.getElementById("nhs-hospitals-data");
    if (!el || !dataEl || typeof L === "undefined") return;

    var hospitals = [];
    try {
        hospitals = JSON.parse(dataEl.textContent) || [];
    } catch (e) {
        return;
    }
    if (!hospitals.length) return;

    function esc(text) {
        var div = document.createElement("div");
        div.textContent = text;
        return div.innerHTML;
    }

    var map = L.map(el);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution:
            '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);

    var bounds = [];
    hospitals.forEach(function (h) {
        if (h.lat == null || h.lon == null) return;
        var html = "<strong>" + esc(h.name) + "</strong><br>" + esc(h.address) + "<br>" + esc(h.postcode);
        if (h.has_ae) html += "<br>A&amp;E listed";
        html +=
            '<br><a href="https://www.google.com/maps/search/?api=1&query=' +
            h.lat +
            "," +
            h.lon +
            '" target="_blank" rel="noopener">Directions ↗</a>';
        L.marker([h.lat, h.lon]).addTo(map).bindPopup(html);
        bounds.push([h.lat, h.lon]);
    });

    if (bounds.length) map.fitBounds(bounds, { padding: [30, 30] });
})();
