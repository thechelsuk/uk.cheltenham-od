(function () {
    var el = document.getElementById("childcare-map");
    var dataEl = document.getElementById("childcare-data");
    if (!el || !dataEl || typeof L === "undefined") return;

    var providers = [];
    try {
        providers = JSON.parse(dataEl.textContent) || [];
    } catch (e) {
        return;
    }
    if (!providers.length) return;

    var map = L.map(el);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);

    var bounds = [];
    providers.forEach(function (p) {
        if (p.lat == null || p.lon == null) return;
        var html = "<strong>" + p.name + "</strong><br>" + p.type;
        if (p.places) html += ", " + p.places_display + " places";
        html += "<br>" + p.address + ", " + p.postcode;
        html += '<br>Ofsted: <a href="' + p.ofsted_url + '" target="_blank" rel="noopener">' + p.latest.outcome + "</a>";
        if (p.latest.date) html += " (" + p.latest.date + ")";
        L.marker([p.lat, p.lon]).addTo(map).bindPopup(html);
        bounds.push([p.lat, p.lon]);
    });

    if (bounds.length) map.fitBounds(bounds, { padding: [30, 30] });
})();
