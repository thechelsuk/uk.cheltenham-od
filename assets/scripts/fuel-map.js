(function () {
    var el = document.getElementById("fuel-map");
    var dataEl = document.getElementById("fuel-map-data");
    if (!el || !dataEl || typeof L === "undefined") return;

    var points = [];
    try {
        points = JSON.parse(dataEl.textContent) || [];
    } catch (e) {
        return;
    }
    if (!points.length) return;

    var map = L.map(el);
    CODMap.tiles(map);


    var markers = points.map(function (p) {
        var marker = p.cheapest
            ? L.marker([p.lat, p.lon], { icon: CODMap.accentIcon(), zIndexOffset: 1000 })
            : L.marker([p.lat, p.lon]);
        return marker.bindPopup(p.popup + CODMap.directions(p.lat, p.lon));
    });
    var group = L.featureGroup(markers).addTo(map);
    map.fitBounds(group.getBounds().pad(0.15));

    CODMap.linkPins(map, el);
})();
