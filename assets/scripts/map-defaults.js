// Site-wide Leaflet defaults, loaded straight after Leaflet by
// _includes/leaflet.html so every map shares one base layer:
// - OpenStreetMap's standard tiles, from tile.openstreetmap.org (the old
//   a/b/c subdomains are no longer recommended);
// - the attribution OpenStreetMap's licence asks for, linking to its
//   copyright page.
// Each map script calls CODMap.tiles(map) instead of adding its own layer.
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
    };
})();
