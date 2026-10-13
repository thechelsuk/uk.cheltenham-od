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
    CODMap.tiles(map);

    var markers = items
        .filter(function (item) {
            return item.lat != null && item.lon != null;
        })
        .map(function (item) {
            var html = "<strong>" + (item.address || "Council asset") + "</strong>";
            if (item.holding_type) html += "<br>" + item.holding_type;
            if (item.tenure_type) html += "<br>" + item.tenure_type;
            html += CODMap.directions(item.lat, item.lon);
            return L.marker([item.lat, item.lon]).bindPopup(html);
        });

    if (!markers.length) return;

    var group = L.featureGroup(markers).addTo(map);
    map.fitBounds(group.getBounds().pad(0.15));

    CODMap.linkPins(map, el);
})();
