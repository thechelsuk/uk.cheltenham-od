// Site-wide Leaflet defaults, loaded straight after Leaflet by
// _includes/leaflet.html so every map shares one base layer:
// - OpenStreetMap's standard tiles, from tile.openstreetmap.org (the old
//   a/b/c subdomains are no longer recommended);
// - the attribution OpenStreetMap's licence asks for, linking to its
//   copyright page.
// Each map script calls CODMap.tiles(map) instead of adding its own layer.
//
// CODMap.accentIcon() is a pin in the page's accent colour, for markers a
// page highlights (cheapest fuel, planned power cuts, discharging overflows).
// CODMap.directions(lat, lng) returns a "Directions" link for a popup, and
// CODMap.linkPins(map, el, groups) makes table pins (pin.html) show their item
// on the page map instead of opening Google Maps. A pin matches the marker at
// its coordinates, or failing that the nearest line within 75 m (a street on
// the permit zones map); unmatched pins keep their Google Maps link. groups
// lists any toggleable layer groups not on the map at load, which are switched
// on when one of their items is shown.
(function () {
    if (typeof L === "undefined") return;

    var accentIcon;

    window.CODMap = {
        tiles: function (map) {
            return L.tileLayer(
                "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
                {
                    maxZoom: 19,
                    attribution:
                        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
                },
            ).addTo(map);
        },

        accentIcon: function () {
            if (!accentIcon) {
                var accent =
                    getComputedStyle(document.body)
                        .getPropertyValue("--accent")
                        .trim() || "#ca3393";
                accentIcon = L.divIcon({
                    className: "accent-map-pin",
                    html:
                        '<svg width="25" height="41" viewBox="0 0 25 41" xmlns="http://www.w3.org/2000/svg">' +
                        '<path fill="' +
                        accent +
                        '" stroke="#000" stroke-opacity="0.3" ' +
                        'd="M12.5 0C5.6 0 0 5.6 0 12.5c0 9.4 12.5 28.5 12.5 28.5S25 21.9 25 12.5C25 5.6 19.4 0 12.5 0z"/>' +
                        '<circle cx="12.5" cy="12.5" r="5.5" fill="#fff"/>' +
                        "</svg>",
                    iconSize: [25, 41],
                    iconAnchor: [12, 41],
                    popupAnchor: [1, -34],
                });
            }
            return accentIcon;
        },

        directions: function (lat, lng) {
            return (
                '<br><a href="https://www.google.com/maps/dir/?api=1&destination=' +
                lat +
                "," +
                lng +
                '" target="_blank" rel="noopener">Directions ↗</a>'
            );
        },

        linkPins: function (map, el, groups) {
            var candidates = [];
            map.eachLayer(function (layer) {
                candidates.push({ layer: layer });
            });
            (groups || []).forEach(function (group) {
                group.eachLayer(function (layer) {
                    candidates.push({ layer: layer, group: group });
                });
            });

            // Lines prefer one whose popup names the pin (a street sits near
            // its neighbours), then the nearest.
            function find(point, name) {
                var best = null;
                var bestScore = 75;
                candidates.forEach(function (c) {
                    var layer = c.layer;
                    if (!layer.getPopup || !layer.getPopup()) return;
                    var dist;
                    if (layer.getLatLng) {
                        dist = map.distance(point, layer.getLatLng());
                        if (dist > 1) return;
                    } else if (
                        layer instanceof L.Polyline &&
                        !(layer instanceof L.Polygon)
                    ) {
                        if (!map.hasLayer(layer)) return;
                        var closest = layer.closestLayerPoint(
                            map.latLngToLayerPoint(point),
                        );
                        if (!closest) return;
                        dist = map.distance(
                            point,
                            map.layerPointToLatLng(closest),
                        );
                        var content = String(layer.getPopup().getContent());
                        if (dist < 300 && content.indexOf(name) !== -1)
                            dist -= 1000;
                    } else {
                        return;
                    }
                    if (dist < bestScore) {
                        best = c;
                        bestScore = dist;
                    }
                });
                return best;
            }

            document
                .querySelectorAll("a[data-map-pin]:not([data-map-linked])")
                .forEach(function (link) {
                    var coords = link.getAttribute("data-map-pin").split(",");
                    var name = link
                        .getAttribute("aria-label")
                        .replace(/^View |\s+on Google Maps$/g, "")
                        .replace(/\s+/g, " ");
                    var match = find(
                        L.latLng(parseFloat(coords[0]), parseFloat(coords[1])),
                        name,
                    );
                    if (!match) return;
                    var layer = match.layer;
                    var label = link
                        .getAttribute("aria-label")
                        .replace("on Google Maps", "on the map");
                    link.setAttribute("data-map-linked", "");
                    link.setAttribute("aria-label", label);
                    link.setAttribute("title", label);
                    link.removeAttribute("target");
                    link.addEventListener("click", function (event) {
                        event.preventDefault();
                        if (match.group && !map.hasLayer(match.group))
                            match.group.addTo(map);
                        var reduce =
                            window.matchMedia &&
                            window.matchMedia(
                                "(prefers-reduced-motion: reduce)",
                            ).matches;
                        el.scrollIntoView({
                            behavior: reduce ? "auto" : "smooth",
                            block: "center",
                        });
                        // Lines fit their length; points zoom in.
                        if (layer.getBounds) {
                            map.fitBounds(layer.getBounds(), {
                                padding: [30, 30],
                            });
                        } else {
                            map.setView(
                                layer.getLatLng(),
                                Math.max(map.getZoom(), 16),
                            );
                        }
                        layer.openPopup();
                    });
                });
        },
    };
})();
