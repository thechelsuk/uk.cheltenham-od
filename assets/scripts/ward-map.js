(function () {
    var el = document.getElementById("ward-map");
    var dataEl = document.getElementById("ward-map-data");
    if (!el || !dataEl || typeof L === "undefined") return;

    var ward = null;
    try {
        ward = JSON.parse(dataEl.textContent);
    } catch (e) {
        return;
    }
    if (!ward || !ward.boundary || !ward.boundary.length) return;

    function escapeHtml(text) {
        var div = document.createElement("div");
        div.textContent = text == null ? "" : text;
        return div.innerHTML;
    }

    var map = L.map(el, { zoomSnap: 0.25 });
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);

    var outline = L.polygon(ward.boundary, { color: "#1d4ed8", weight: 3, fillOpacity: 0.06 }).addTo(map);
    map.fitBounds(outline.getBounds(), { padding: [20, 20] });

    var colours = {
        "Health": "#dc2626",
        "Schools": "#7c3aed",
        "Parks and Play": "#16a34a",
        "Everyday Services": "#0891b2",
        "Getting Around": "#ea580c",
        "Food and Drink": "#db2777",
        "Heritage": "#a16207",
    };
    // Health and schools start switched on; the busier layers are opt-in.
    var startOn = { "Health": true, "Schools": true, "Parks and Play": true };

    var overlays = {};
    (ward.services || []).forEach(function (service) {
        if (!service.items || !service.items.length) return;
        var colour = colours[service.group] || "#475569";
        var layer = L.layerGroup();
        service.items.forEach(function (item) {
            var html =
                "<strong>" + escapeHtml(item.name) + "</strong><br>" +
                escapeHtml(service.label) +
                (item.type ? "<br>" + escapeHtml(item.type) : "") +
                (item.detail ? "<br>" + escapeHtml(item.detail) : "") +
                (item.address ? "<br>" + escapeHtml(item.address) : "") +
                "<br>" + item.distance_miles + " mi from the middle of the ward" +
                (item.in_ward ? "" : " (outside the ward)");
            L.circleMarker([item.lat, item.lon], {
                radius: item.in_ward ? 8 : 6,
                color: colour,
                weight: item.in_ward ? 3 : 1,
                fillColor: colour,
                fillOpacity: item.in_ward ? 0.85 : 0.4,
            })
                .bindPopup(html)
                .addTo(layer);
        });
        overlays['<span style="color:' + colour + '">&#9679;</span> ' + escapeHtml(service.label)] = layer;
        if (startOn[service.group]) layer.addTo(map);
    });

    L.control.layers(null, overlays, { collapsed: true }).addTo(map);
})();
