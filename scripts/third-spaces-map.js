(function () {
    var locations = JSON.parse(
        document.getElementById("third-spaces-data").textContent,
    );
    var centre = JSON.parse(
        document.getElementById("third-spaces-centre").textContent,
    );

    var map = L.map("third-spaces-map").setView(
        [centre.latitude, centre.longitude],
        13,
    );

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution: "© OpenStreetMap contributors",
    }).addTo(map);

    var bounds = [];
    locations.forEach(function (loc) {
        if (loc.latitude == null || loc.longitude == null) return;
        var marker = L.marker([loc.latitude, loc.longitude]).addTo(map);
        var html = "<strong>" + loc.name + "</strong>";
        if (loc.address) html += "<br>" + loc.address;
        if (loc.website)
            html += '<br><a href="' + loc.website + '">Website</a>';
        marker.bindPopup(html);
        bounds.push([loc.latitude, loc.longitude]);
    });

    if (bounds.length) map.fitBounds(bounds, { padding: [30, 30] });
})();
