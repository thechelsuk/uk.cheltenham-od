(function () {
    var el = document.getElementById("roadworks-map");
    var dataEl = document.getElementById("roadworks-data");
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
        return String(iso).replace("T", " ");
    }

    var map = L.map(el);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution:
            '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);

    // No works to plot: still show Cheltenham rather than a blank grey box.
    if (!works.length) {
        map.setView([51.899, -2.078], 11);
        return;
    }

    var bounds = [];
    works.forEach(function (w) {
        if (w.lat == null || w.lon == null) return;
        var html = "<strong>" + esc((w.roads || []).join(", ")) + "</strong>";
        html += "<br>" + esc(w.description);
        html +=
            "<br>" +
            (w.in_progress ? "In progress" : "Planned") +
            ": " +
            formatDate(w.start) +
            " to " +
            formatDate(w.end);
        if (w.expected_delay) html += "<br>Expected delay: " + esc(w.expected_delay);
        L.marker([w.lat, w.lon]).addTo(map).bindPopup(html);
        bounds.push([w.lat, w.lon]);
    });

    if (bounds.length) map.fitBounds(bounds, { padding: [30, 30], maxZoom: 13 });
})();
