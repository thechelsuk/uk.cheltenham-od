(function () {
    var mapEl = document.getElementById("fms-map");
    var dataEl = document.getElementById("fms-data");
    if (!mapEl || !dataEl || typeof L === "undefined") return;

    var items = [];
    try {
        items = JSON.parse(dataEl.textContent) || [];
    } catch (e) {
        return;
    }

    // Cheltenham town centre, used when there are no reports to plot.
    var CHELTENHAM = [51.897991, -2.071308];

    var map = L.map(mapEl);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);

    function escapeHtml(text) {
        var div = document.createElement("div");
        div.textContent = text == null ? "" : String(text);
        return div.innerHTML;
    }

    var bounds = [];
    items.forEach(function (item) {
        if (item.lat == null || item.lon == null) return;
        var html =
            "<strong>" + escapeHtml(item.title) + "</strong><br>" +
            escapeHtml(item.group) + "<br>" +
            '<a href="' + escapeHtml(item.url) + '" rel="noopener">View on FixMyStreet</a>';
        L.marker([item.lat, item.lon]).addTo(map).bindPopup(html);
        bounds.push([item.lat, item.lon]);
    });

    if (bounds.length) map.fitBounds(bounds, { padding: [30, 30], maxZoom: 15 });
    else map.setView(CHELTENHAM, 12);
})();
