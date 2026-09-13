(function () {
    var el = document.getElementById("parkrun-map");
    var dataEl = document.getElementById("parkrun-data");
    if (!el || !dataEl || typeof L === "undefined") return;

    var events = [];
    try {
        events = JSON.parse(dataEl.textContent) || [];
    } catch (e) {
        return;
    }
    if (!events.length) return;

    var map = L.map(el);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution:
            '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);

    var bounds = [];
    events.forEach(function (e) {
        if (e.lat == null || e.lon == null) return;
        var html = "<strong>" + (e.name || "parkrun") + "</strong>";
        if (e.location) html += "<br>" + e.location;
        if (e.distance) html += "<br>" + e.distance;
        if (e.event_page) {
            html +=
                '<br><a href="' +
                e.event_page +
                '" target="_blank" rel="noopener">Event page ↗</a>';
        }
        L.marker([e.lat, e.lon]).addTo(map).bindPopup(html);
        bounds.push([e.lat, e.lon]);
    });

    if (bounds.length) map.fitBounds(bounds, { padding: [30, 30] });
})();
