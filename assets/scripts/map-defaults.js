// Site-wide Leaflet defaults, loaded straight after Leaflet by
// _includes/leaflet.html so every map shares one base layer:
// - OpenStreetMap's standard tiles, from tile.openstreetmap.org (the old
//   a/b/c subdomains are no longer recommended);
// - the attribution OpenStreetMap's licence asks for, linking to its
//   copyright page.
// Each map script calls CODMap.tiles(map) instead of adding its own layer.
//
// CODMap.directions(lat, lng) returns a "Directions" link for a popup, and
// CODMap.linkPins(map, el, layers) makes table pins (pin.html with a
// map_target) show their item on the page map instead of opening Google Maps.
// layers maps each map_target id to its marker or shape.
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

        linkPins: function (map, el, layers) {
            document
                .querySelectorAll("[data-map-target]")
                .forEach(function (link) {
                    var layer = layers[link.getAttribute("data-map-target")];
                    if (!layer) return;
                    var label = link
                        .getAttribute("aria-label")
                        .replace("on Google Maps", "on the map");
                    link.setAttribute("aria-label", label);
                    link.setAttribute("title", label);
                    link.removeAttribute("target");
                    link.addEventListener("click", function (event) {
                        event.preventDefault();
                        var reduce =
                            window.matchMedia &&
                            window.matchMedia(
                                "(prefers-reduced-motion: reduce)",
                            ).matches;
                        el.scrollIntoView({
                            behavior: reduce ? "auto" : "smooth",
                            block: "center",
                        });
                        // Shapes (routes, zones) fit their outline; points zoom in.
                        if (layer.getBounds) {
                            map.fitBounds(layer.getBounds(), {
                                padding: [30, 30],
                            });
                        } else {
                            map.setView(layer.getLatLng(), 16);
                        }
                        layer.openPopup();
                    });
                });
        },
    };
})();
