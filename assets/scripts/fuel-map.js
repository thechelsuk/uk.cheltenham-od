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
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution:
            '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);

    var accent = getComputedStyle(document.body)
        .getPropertyValue("--accent")
        .trim() || "#ca3393";

    var cheapestIcon = L.divIcon({
        className: "fuel-map-pin fuel-map-pin-cheapest",
        html:
            '<svg width="25" height="41" viewBox="0 0 25 41" xmlns="http://www.w3.org/2000/svg">' +
            '<path fill="' + accent + '" stroke="#000" stroke-opacity="0.3" ' +
            'd="M12.5 0C5.6 0 0 5.6 0 12.5c0 9.4 12.5 28.5 12.5 28.5S25 21.9 25 12.5C25 5.6 19.4 0 12.5 0z"/>' +
            '<circle cx="12.5" cy="12.5" r="5.5" fill="#fff"/>' +
            "</svg>",
        iconSize: [25, 41],
        iconAnchor: [12, 41],
        popupAnchor: [1, -34],
    });

    var markers = points.map(function (p) {
        var marker = p.cheapest
            ? L.marker([p.lat, p.lon], { icon: cheapestIcon, zIndexOffset: 1000 })
            : L.marker([p.lat, p.lon]);
        return marker.bindPopup(p.popup);
    });
    var group = L.featureGroup(markers).addTo(map);
    map.fitBounds(group.getBounds().pad(0.15));
})();
