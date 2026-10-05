(function () {
    var el = document.getElementById("care-homes-map");
    var dataEl = document.getElementById("care-homes-data");
    if (!el || !dataEl || typeof L === "undefined") return;

    var homes = [];
    try {
        homes = JSON.parse(dataEl.textContent) || [];
    } catch (e) {
        return;
    }
    if (!homes.length) return;

    var map = L.map(el);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);

    var bounds = [];
    homes.forEach(function (h) {
        if (h.lat == null || h.lon == null) return;
        var html = '<strong><a href="/cheltenham-care-homes/' + h.slug + '">' + h.name + "</a></strong><br>";
        html += (h.kind === "nursing_home" ? "Nursing home" : "Residential home") + "<br>";
        html += h.address + ", " + h.postcode + "<br>";
        html += 'CQC: <a href="' + h.url + '" target="_blank" rel="noopener">' + (h.overall || "Not yet rated") + "</a>";
        if (h.published) html += " (" + h.published + ")";
        L.marker([h.lat, h.lon]).addTo(map).bindPopup(html);
        bounds.push([h.lat, h.lon]);
    });

    if (bounds.length) map.fitBounds(bounds, { padding: [30, 30] });
})();
