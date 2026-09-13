(function () {
    var el = document.getElementById("catchment-map");
    var legendEl = document.getElementById("catchment-legend");
    var dataEl = document.getElementById("catchment-data");
    if (!el || !dataEl || typeof L === "undefined" || typeof d3 === "undefined") return;

    var schools = [];
    try {
        schools = JSON.parse(dataEl.textContent) || [];
    } catch (e) {
        return;
    }

    // Cheltenham town centre — schools further than this are a different
    // village or town (e.g. Winchcombe, Bourton-on-the-Water) sharing a
    // Cheltenham postcode district, and including them would stretch the
    // "nearest school" zones across open countryside rather than reflect
    // choices within Cheltenham itself. Set per-page via data-max-miles.
    var CENTRE = { lat: 51.8994, lon: -2.0783 };
    var MAX_MILES = parseFloat(el.dataset.maxMiles) || 4.5;

    function milesBetween(a, b) {
        var R = 3958.8;
        var dLat = ((b.lat - a.lat) * Math.PI) / 180;
        var dLon = ((b.lon - a.lon) * Math.PI) / 180;
        var lat1 = (a.lat * Math.PI) / 180;
        var lat2 = (b.lat * Math.PI) / 180;
        var x =
            Math.sin(dLat / 2) * Math.sin(dLat / 2) +
            Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLon / 2) * Math.sin(dLon / 2);
        return R * 2 * Math.asin(Math.sqrt(x));
    }

    var points = schools
        .filter(function (s) {
            return s.lat != null && s.lon != null;
        })
        .filter(function (s) {
            return milesBetween(CENTRE, s) <= MAX_MILES;
        })
        .sort(function (a, b) {
            return a.name.localeCompare(b.name);
        });

    if (points.length < 2) return;

    // Golden-angle hue rotation gives N visually distinct colours without
    // needing a hand-picked palette sized to the school count (7 for
    // secondary, 30+ for primary).
    function colorForIndex(i) {
        var hue = (i * 137.508) % 360;
        return "hsl(" + hue.toFixed(0) + ", 62%, 42%)";
    }

    var map = L.map(el);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution:
            '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);

    // Voronoi cells computed in lon/lat space (flat-earth approximation —
    // fine at town scale) and clipped to a box around the included schools.
    var lons = points.map(function (p) { return p.lon; });
    var lats = points.map(function (p) { return p.lat; });
    var padLon = 0.08;
    var padLat = 0.05;
    var bounds = [
        Math.min.apply(null, lons) - padLon,
        Math.min.apply(null, lats) - padLat,
        Math.max.apply(null, lons) + padLon,
        Math.max.apply(null, lats) + padLat,
    ];

    var delaunay = d3.Delaunay.from(points.map(function (p) { return [p.lon, p.lat]; }));
    var voronoi = delaunay.voronoi(bounds);

    var legendHtml = "";
    var group = [];

    points.forEach(function (p, i) {
        var color = colorForIndex(i);
        var cell = voronoi.cellPolygon(i);
        if (cell) {
            var latLngs = cell.map(function (pt) { return [pt[1], pt[0]]; });
            var polygon = L.polygon(latLngs, {
                color: color,
                weight: 1,
                fillColor: color,
                fillOpacity: 0.28,
            }).addTo(map);
            polygon.bindPopup(popupHtml(p));
            group.push(polygon);
        }

        var marker = L.circleMarker([p.lat, p.lon], {
            radius: 6,
            color: "#ffffff",
            weight: 2,
            fillColor: color,
            fillOpacity: 1,
        }).addTo(map);
        marker.bindPopup(popupHtml(p));
        group.push(marker);

        legendHtml +=
            '<span class="catchment-legend-item"><span class="catchment-swatch" style="background:' +
            color +
            '"></span>' +
            (p.name || "School") +
            "</span> ";
    });

    if (legendEl) legendEl.innerHTML = legendHtml;

    function popupHtml(p) {
        var html = "<strong>" + (p.name || "School") + "</strong>";
        if (p.type) html += "<br>" + p.type;
        if (p.address) html += "<br>" + p.address;
        var link = p.website || p.urn_url;
        if (link) {
            html +=
                '<br><a href="' +
                link +
                '" target="_blank" rel="noopener">More details ↗</a>';
        }
        html += '<br><small>Nearest by straight-line distance only</small>';
        return html;
    }

    if (group.length) {
        map.fitBounds(L.featureGroup(group).getBounds().pad(0.1));
    }
})();
