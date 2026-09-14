(function () {
    var el = document.getElementById("council-land-and-assets-map");
    var dataEl = document.getElementById("council-land-and-assets-data");
    if (!el || !dataEl || typeof L === "undefined") return;

    var items = [];
    try {
        items = JSON.parse(dataEl.textContent) || [];
    } catch (e) {
        return;
    }
    if (!items.length) return;

    var map = L.map(el);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);

    var markers = items
        .filter(function (item) {
            return item.lat != null && item.lon != null;
        })
        .map(function (item) {
            var html = "<strong>" + (item.address || "Council asset") + "</strong>";
            if (item.holding_type) html += "<br>" + item.holding_type;
            if (item.tenure_type) html += "<br>" + item.tenure_type;
            return L.marker([item.lat, item.lon]).bindPopup(html);
        });

    if (!markers.length) return;

    var group = L.featureGroup(markers).addTo(map);
    map.fitBounds(group.getBounds().pad(0.15));
})();
