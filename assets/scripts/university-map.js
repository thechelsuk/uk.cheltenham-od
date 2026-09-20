(function () {
    var el = document.getElementById("university-map");
    var dataEl = document.getElementById("university-data");
    var centreEl = document.getElementById("university-centre");
    if (!el || !dataEl || typeof L === "undefined") return;

    var locations = [];
    var centre = { latitude: 51.89, longitude: -2.16 };
    try {
        locations = JSON.parse(dataEl.textContent) || [];
        if (centreEl) centre = JSON.parse(centreEl.textContent) || centre;
    } catch (e) {
        return;
    }
    if (!locations.length) return;

    var map = L.map(el).setView([centre.latitude, centre.longitude], 12);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);

    var bounds = [];
    locations.forEach(function (loc) {
        if (loc.latitude == null || loc.longitude == null) return;
        var html = "<strong>" + loc.name + "</strong><br>" + loc.address + ", " + loc.postcode;
        if (loc.description) html += "<br>" + loc.description;
        html += '<br><a href="' + loc.website + '">Campus information</a>';
        html += ' &middot; <a href="' + loc.campus_map + '">Interactive map</a>';
        L.marker([loc.latitude, loc.longitude]).addTo(map).bindPopup(html);
        bounds.push([loc.latitude, loc.longitude]);
    });

    if (bounds.length) map.fitBounds(bounds, { padding: [30, 30] });
})();
