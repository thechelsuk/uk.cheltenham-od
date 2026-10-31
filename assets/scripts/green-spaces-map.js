// Map of Cheltenham's green spaces (OS Open Greenspace): every site drawn as
// its outline, shaded by group in the colour-blind-safe Okabe-Ito palette.
// Each group is its own layer, so the layer control can hide it, and the
// legend and every popup name the group, so colour is never the only clue.
(function () {
    var el = document.getElementById("green-spaces-map");
    var dataEl = document.getElementById("green-spaces-data");
    var legend = document.getElementById("green-spaces-legend");
    if (!el || !dataEl || typeof L === "undefined") return;

    var data = {};
    try {
        data = JSON.parse(dataEl.textContent) || {};
    } catch (e) {
        return;
    }
    var sites = data.sites || [];
    if (!sites.length) return;

    var COLOURS = {
        parks: "#009E73",
        sports: "#0072B2",
        play: "#CC79A7",
        allotments: "#E69F00",
        burial: "#555555",
    };

    function esc(text) {
        var div = document.createElement("div");
        div.textContent = text == null ? "" : text;
        return div.innerHTML;
    }

    var map = L.map(el);
    CODMap.tiles(map);

    var layers = {};
    var overlays = {};
    (data.groups || []).forEach(function (g) {
        layers[g.id] = L.featureGroup();
        overlays[esc(g.name)] = layers[g.id];
    });

    var bounds = [];
    sites.forEach(function (s) {
        var layer = layers[s.group];
        if (!layer) return;
        var colour = COLOURS[s.group] || "#555555";
        var html =
            "<strong>" +
            esc(s.name) +
            "</strong><br>" +
            esc(s.type) +
            ", " +
            esc(s.ward) +
            " ward" +
            "<br>" +
            s.hectares +
            " hectares";
        if (s.access_points) {
            html +=
                "<br>" +
                s.access_points +
                (s.access_points === 1 ? " way in" : " ways in");
            if (s.vehicle_access)
                html += ", " + s.vehicle_access + " with vehicle access";
        }
        html += CODMap.directions(s.lat, s.lon);
        L.polygon(s.polygons, {
            color: colour,
            fillColor: colour,
            fillOpacity: 0.45,
            weight: 1,
        })
            .bindPopup(html)
            .addTo(layer);
        // An invisible point at the site's middle lets the table's map pins find it.
        L.circleMarker([s.lat, s.lon], {
            radius: 4,
            opacity: 0,
            fillOpacity: 0,
        })
            .bindPopup(html)
            .addTo(layer);
        bounds.push([s.lat, s.lon]);
    });

    // Pins are linked while the groups are still off the map, so each pin
    // knows its group and switches it back on if the reader has hidden it.
    var groups = Object.keys(layers).map(function (id) {
        return layers[id];
    });
    CODMap.linkPins(map, el, groups);
    groups.forEach(function (group) {
        group.addTo(map);
    });

    if (bounds.length) map.fitBounds(bounds, { padding: [20, 20] });
    L.control.layers(null, overlays, { collapsed: true }).addTo(map);

    if (legend) {
        legend.innerHTML = (data.groups || [])
            .map(function (g) {
                return (
                    '<span><i class="tier-swatch" style="background:' +
                    (COLOURS[g.id] || "#555555") +
                    '"></i> ' +
                    esc(g.name) +
                    "</span>"
                );
            })
            .join("");
    }
})();
