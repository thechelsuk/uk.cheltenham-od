(function () {
    var el = document.getElementById("street-works-map");
    var dataEl = document.getElementById("street-works-data");
    if (!el || !dataEl || typeof L === "undefined") return;

    var works = [];
    try {
        works = JSON.parse(dataEl.textContent) || [];
    } catch (e) {
        return;
    }

    function esc(text) {
        var div = document.createElement("div");
        div.textContent = text;
        return div.innerHTML;
    }

    // "2026-09-21T21:00" -> "2026-09-21 21:00", matching the table
    function formatDate(iso) {
        return iso ? String(iso).replace("T", " ") : "";
    }

    var map = L.map(el);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution:
            '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);

    // No works to plot: still show Cheltenham rather than a blank grey box.
    if (!works.length) {
        map.setView([51.899, -2.078], 12);
        return;
    }

    var bounds = [];
    works.forEach(function (w) {
        if (w.lat == null || w.lon == null) return;
        var html = "<strong>" + esc(w.street) + "</strong>";
        if (w.area) html += ", " + esc(w.area);
        html += "<br>" + esc(w.kind) + " works: " + esc(w.status);
        if (w.traffic_management) html += "<br>" + esc(w.traffic_management);
        if (w.start) html += "<br>" + formatDate(w.start) + (w.end ? " to " + formatDate(w.end) : "");
        if (w.promoter) html += "<br>" + esc(w.promoter);
        L.marker([w.lat, w.lon]).addTo(map).bindPopup(html);
        bounds.push([w.lat, w.lon]);
    });

    if (bounds.length) map.fitBounds(bounds, { padding: [30, 30], maxZoom: 15 });
})();
