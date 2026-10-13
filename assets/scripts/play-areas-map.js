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
    CODMap.tiles(map);

    var bounds = [];
    playAreas.forEach(function (p) {
        if (p.lat == null || p.lon == null) return;
        var html = "<strong>" + esc(p.name) + "</strong>";
        if (p.operator) html += "<br>Run by " + esc(p.operator);
        if (p.theme) html += "<br>" + esc(p.theme) + " play";
        if (p.surface) html += "<br>" + esc(p.surface) + " surface";
        html += CODMap.directions(p.lat, p.lon);
        L.marker([p.lat, p.lon]).addTo(map).bindPopup(html);
        bounds.push([p.lat, p.lon]);
    });

    if (bounds.length) map.fitBounds(bounds, { padding: [30, 30] });

    CODMap.linkPins(map, el);
})();
