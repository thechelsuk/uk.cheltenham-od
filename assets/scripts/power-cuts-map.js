(function () {
    var el = document.getElementById("power-cuts-map");
    var dataEl = document.getElementById("power-cuts-data");
    if (!el || !dataEl || typeof L === "undefined") return;

    var incidents = [];
    try {
        incidents = JSON.parse(dataEl.textContent) || [];
    } catch (e) {
        return;
    }

    // Cheltenham town centre — used to keep the map showing Cheltenham even
    // when there are no current power cuts to plot.
    var CHELTENHAM = [51.897991, -2.071308];

    var map = L.map(el);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);

    var bounds = [];
    incidents.forEach(function (incident) {
        if (incident.lat == null || incident.lon == null) return;
        var html =
            "<strong>" + (incident.category || "Power cut") + "</strong>" +
            "<br>" + (incident.status || "") +
            (incident.confirmed_off ? "<br>" + incident.confirmed_off + " properties affected" : "") +
            (incident.postcodes && incident.postcodes.length ? "<br>" + incident.postcodes.join(", ") : "");
        L.marker([incident.lat, incident.lon]).addTo(map).bindPopup(html);
        bounds.push([incident.lat, incident.lon]);
    });

    if (bounds.length) {
        map.fitBounds(bounds, { padding: [30, 30] });
    } else {
        map.setView(CHELTENHAM, 13);
    }
})();
