(function () {
    var el = document.getElementById("opticians-map");
    var dataEl = document.getElementById("opticians-data");
    if (!el || !dataEl || typeof L === "undefined") return;

    var sites = [];
    try {
        sites = JSON.parse(dataEl.textContent) || [];
    } catch (e) {
        return;
    }
    if (!sites.length) return;

    var map = L.map(el);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);

    var bounds = [];
    sites.forEach(function (p) {
        if (p.lat == null || p.lon == null) return;
        var html = "<strong>" + p.name + "</strong><br>" + p.address + (p.postcode ? ", " + p.postcode : "");
        L.marker([p.lat, p.lon]).addTo(map).bindPopup(html);
        bounds.push([p.lat, p.lon]);
    });

    if (bounds.length) map.fitBounds(bounds, { padding: [30, 30] });
})();
