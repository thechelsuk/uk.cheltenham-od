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

    // Unplanned faults get the standard pin; planned work gets a pin in the
    // page's accent colour (as on the fuel prices map).
    var accent = getComputedStyle(document.body).getPropertyValue("--accent").trim() || "#ca3393";
    var plannedIcon = L.divIcon({
        className: "power-cuts-map-pin",
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

    var bounds = [];
    var markers = {};
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
        var marker = incident.planned
            ? L.marker([incident.lat, incident.lon], { icon: plannedIcon, zIndexOffset: 500 })
            : L.marker([incident.lat, incident.lon]);
        markers[incident.fault_id] = marker.addTo(map).bindPopup(html);
        bounds.push([incident.lat, incident.lon]);
    });

    if (bounds.length) {
        map.fitBounds(bounds, { padding: [30, 30] });
    } else {
        map.setView(CHELTENHAM, 13);
    }

    // Table pins show their cut on this map instead of opening Google Maps.
    CODMap.linkPins(map, el, markers);
})();
