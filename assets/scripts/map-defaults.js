// Site-wide Leaflet defaults, loaded straight after Leaflet by
// _includes/leaflet.html so every map shares one base layer:
// - OpenStreetMap's standard tiles, from tile.openstreetmap.org (the old
//   a/b/c subdomains are no longer recommended);
// - the attribution OpenStreetMap's licence asks for, linking to its
//   copyright page.
// Each map script calls CODMap.tiles(map) instead of adding its own layer.
//
// CODMap.directions(lat, lng) returns a "Directions" link for a popup, and
// CODMap.linkPins(map, el, groups) makes table pins (pin.html) show their item
// on the page map instead of opening Google Maps. A pin matches the marker at
// its coordinates, or failing that the nearest line within 75 m (a street on
// the permit zones map); unmatched pins keep their Google Maps link. groups
// lists any toggleable layer groups not on the map at load, which are switched
// on when one of their items is shown.
(function () {
    if (typeof L === "undefined") return;

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
