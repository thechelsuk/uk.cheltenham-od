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
    CODMap.tiles(map);

    var bounds = [];
    hospitals.forEach(function (h) {
        if (h.lat == null || h.lon == null) return;
        var html = "<strong>" + esc(h.name) + "</strong><br>" + esc(h.address) + "<br>" + esc(h.postcode);
        if (h.has_ae) html += "<br>A&amp;E listed";
        html += CODMap.directions(h.lat, h.lon);
        L.marker([h.lat, h.lon]).addTo(map).bindPopup(html);
        bounds.push([h.lat, h.lon]);
    });

    if (bounds.length) map.fitBounds(bounds, { padding: [30, 30] });

    CODMap.linkPins(map, el);
})();
