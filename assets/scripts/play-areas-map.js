(function () {
    var el = document.getElementById("play-areas-map");
    var dataEl = document.getElementById("play-areas-data");
    if (!el || !dataEl || typeof L === "undefined") return;

    var playAreas = [];
    try {
        playAreas = JSON.parse(dataEl.textContent) || [];
    } catch (e) {
        return;
    }
    if (!playAreas.length) return;

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
    playAreas.forEach(function (p) {
        if (p.lat == null || p.lon == null) return;
        var html = "<strong>" + esc(p.name) + "</strong>";
        if (p.operator) html += "<br>Run by " + esc(p.operator);
        if (p.theme) html += "<br>" + esc(p.theme) + " play";
        if (p.surface) html += "<br>" + esc(p.surface) + " surface";
        html +=
            '<br><a href="https://www.google.com/maps/search/?api=1&query=' +
            p.lat +
            "," +
            p.lon +
            '" target="_blank" rel="noopener">Directions ↗</a>';
        L.marker([p.lat, p.lon]).addTo(map).bindPopup(html);
        bounds.push([p.lat, p.lon]);
    });

    if (bounds.length) map.fitBounds(bounds, { padding: [30, 30] });
})();
