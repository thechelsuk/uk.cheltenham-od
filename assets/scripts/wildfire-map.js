(function () {
    var el = document.getElementById("wildfire-map");
    var dataEl = document.getElementById("wildfire-data");
    if (!el || !dataEl || typeof L === "undefined") return;

    var squares = [];
    try {
        squares = JSON.parse(dataEl.textContent) || [];
    } catch (e) {
        return;
    }
    if (!squares.length) return;

    var map = L.map(el);
    CODMap.tiles(map);

    // Squares are outlined and labelled with their level in words, so the
    // map reads the same without relying on colour.
    var bounds = L.latLngBounds([]);
    squares.forEach(function (sq) {
        if (!sq.rings || !sq.rings.length) return;
        var poly = L.polygon(sq.rings, { color: "#52514c", weight: 2, fillOpacity: 0.05 }).addTo(map);
        poly.bindTooltip(
            "<strong>" + sq.ref + "</strong><br>" + sq.rating + " of 5<br>" + sq.label,
            { permanent: true, direction: "center" }
        );
        bounds.extend(poly.getBounds());
    });

    if (bounds.isValid()) map.fitBounds(bounds, { padding: [10, 10] });
})();
