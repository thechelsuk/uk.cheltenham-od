(function () {
    var el = document.getElementById("taxi-ranks-map");
    var dataEl = document.getElementById("taxi-ranks-data");
    if (!el || !dataEl || typeof L === "undefined") return;

    var ranks = [];
    try {
        ranks = JSON.parse(dataEl.textContent) || [];
    } catch (e) {
        return;
    }
    if (!ranks.length) return;

    function esc(text) {
        var div = document.createElement("div");
        div.textContent = text;
        return div.innerHTML;
    }

    var map = L.map(el);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);

    var bounds = [];
    ranks.forEach(function (r) {
        if (r.lat == null || r.lon == null) return;
        var html = "<strong>" + esc(r.name) + " taxi rank</strong>";
        if (r.street && r.street !== r.name) html += "<br>" + esc(r.street);
        if (r.spaces) html += "<br>" + r.spaces + " spaces";
        L.marker([r.lat, r.lon]).addTo(map).bindPopup(html);
        bounds.push([r.lat, r.lon]);
    });

    if (bounds.length) map.fitBounds(bounds, { padding: [30, 30] });
})();
