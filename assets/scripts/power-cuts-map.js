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
    CODMap.tiles(map);


    var bounds = [];
    incidents.forEach(function (incident) {
        if (incident.lat == null || incident.lon == null) return;
        var html =
            "<strong>" + (incident.category || "Power cut") + (incident.planned ? " (Planned)" : "") + "</strong>" +
            "<br>" + (incident.status || "") +
            (incident.planned
                ? "<br>" + (incident.planned_off || incident.confirmed_off || 0) + " properties, " + (incident.planned_start || "").replace("T", " ").slice(0, 16) + " to " + (incident.planned_end || "").replace("T", " ").slice(0, 16)
                : "<br>" + (incident.confirmed_off || 0) + " properties off, " + (incident.restored || 0) + " restored") +
            (incident.postcodes && incident.postcodes.length ? "<br>" + incident.postcodes.join(", ") : "") +
            CODMap.directions(incident.lat, incident.lon);
        // Unplanned faults get the standard pin; planned work gets the accent pin.
        var marker = incident.planned
            ? L.marker([incident.lat, incident.lon], { icon: CODMap.accentIcon(), zIndexOffset: 500 })
            : L.marker([incident.lat, incident.lon]);
        marker.addTo(map).bindPopup(html);
        bounds.push([incident.lat, incident.lon]);
    });

    if (bounds.length) {
        map.fitBounds(bounds, { padding: [30, 30] });
    } else {
        map.setView(CHELTENHAM, 13);
    }

    CODMap.linkPins(map, el);
})();
