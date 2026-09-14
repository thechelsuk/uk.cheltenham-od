(function () {
    var el = document.getElementById("car-parks-map");
    var dataEl = document.getElementById("car-parks-data");
    if (!el || !dataEl || typeof L === "undefined") return;

    var carParks = [];
    try {
        carParks = JSON.parse(dataEl.textContent) || [];
    } catch (e) {
        return;
    }
    if (!carParks.length) return;

    var map = L.map(el);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution:
            '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);

    var bounds = [];
    carParks.forEach(function (c) {
        if (c.lat == null || c.lon == null) return;
        var html = "<strong>" + c.name + "</strong>";
        if (c.operator) html += "<br>" + c.operator;
        html +=
            "<br>" +
            (c.fee === true ? "Fee charged" : c.fee === false ? "Free" : "Fee unknown");
        if (c.capacity) html += "<br>" + c.capacity + " spaces";
        if (c.maxstay) html += "<br>Max stay: " + c.maxstay;
        L.marker([c.lat, c.lon]).addTo(map).bindPopup(html);
        bounds.push([c.lat, c.lon]);
    });

    if (bounds.length) map.fitBounds(bounds, { padding: [30, 30] });
})();
