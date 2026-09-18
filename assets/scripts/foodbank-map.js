(function () {
    var el = document.getElementById("foodbank-map");
    if (!el || typeof L === "undefined") return;

    var nodes = document.querySelectorAll("[data-map-lat]");
    if (!nodes.length) return;

    var map = L.map(el);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);

    // Food banks get the standard pin; locations and donation points are coloured dots.
    var DOT_COLOURS = { location: "#b5561f", donation: "#2a7f3f" };

    function escapeHtml(text) {
        var div = document.createElement("div");
        div.textContent = text == null ? "" : String(text);
        return div.innerHTML;
    }

    var bounds = [];
    Array.prototype.forEach.call(nodes, function (node) {
        var lat = parseFloat(node.getAttribute("data-map-lat"));
        var lon = parseFloat(node.getAttribute("data-map-lon"));
        if (isNaN(lat) || isNaN(lon)) return;

        var kind = node.getAttribute("data-map-kind") || "foodbank";
        var name = node.getAttribute("data-map-name");
        var href = node.getAttribute("data-map-href");
        var html = "<strong>" + escapeHtml(name) + "</strong><br>" + escapeHtml(node.getAttribute("data-map-label") || "");
        if (href) html += '<br><a href="' + escapeHtml(href) + '">View details</a>';

        var marker = DOT_COLOURS[kind]
            ? L.circleMarker([lat, lon], { radius: 8, color: DOT_COLOURS[kind], fillColor: DOT_COLOURS[kind], fillOpacity: 0.8 })
            : L.marker([lat, lon]);
        marker.addTo(map).bindPopup(html);
        bounds.push([lat, lon]);
    });

    if (bounds.length === 1) map.setView(bounds[0], 15);
    else map.fitBounds(bounds, { padding: [30, 30], maxZoom: 15 });
})();
