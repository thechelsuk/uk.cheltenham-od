(function () {
    var el = document.getElementById("flood-zones-map");
    var dataEl = document.getElementById("flood-zones-data");
    if (!el || !dataEl || typeof L === "undefined") return;

    var features = [];
    try {
        features = JSON.parse(dataEl.textContent) || [];
    } catch (e) {
        return;
    }
    if (!features.length) return;

    var STYLES = {
        FZ2: { color: "#5dade2", fillColor: "#85c1e9", fillOpacity: 0.45, weight: 1 },
        FZ3: { color: "#1b4f8a", fillColor: "#2e6db4", fillOpacity: 0.55, weight: 1 },
    };
    var MEANING = {
        FZ2: "Flood Zone 2: a 1 in 100 to 1 in 1,000 chance of river flooding in any year",
        FZ3: "Flood Zone 3: a 1 in 100 or greater chance of river flooding in any year",
    };

    var map = L.map(el).setView([51.899, -2.078], 13);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);

    // Zone 2 first so the darker Zone 3 is drawn on top of it.
    ["FZ2", "FZ3"].forEach(function (zone) {
        features.filter(function (f) { return f.properties.zone === zone; }).forEach(function (f) {
            L.geoJSON(f, { style: STYLES[zone] }).bindPopup(MEANING[zone]).addTo(map);
        });
    });
})();
