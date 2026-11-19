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

    // Latest Ofsted outcome and inspection history page, keyed by school name.
    var ofsted = {};
    var ofstedEl = document.getElementById("catchment-ofsted");
    try {
        ofsted = (ofstedEl && JSON.parse(ofstedEl.textContent)) || {};
    } catch (e) {
        ofsted = {};
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

    function escapeHtml(text) {
        var div = document.createElement("div");
        div.textContent = text == null ? "" : text;
        return div.innerHTML;
    }

    // Only http and https links from the data go into a popup.
    function safeUrl(url) {
        try {
            var parsed = new URL(url, window.location.href);
            return parsed.protocol === "https:" || parsed.protocol === "http:" ? parsed.href : null;
        } catch (e) {
            return null;
        }
    }

    function legendItem(color, label) {
        var item = document.createElement("span");
        var swatch = document.createElement("span");
        swatch.className = "catchment-swatch";
        swatch.style.setProperty("--swatch", color);
        item.appendChild(swatch);
        item.appendChild(document.createTextNode(label));
        return item;
    }

    // Golden-angle hue rotation gives N visually distinct colours without
    // needing a hand-picked palette sized to the school count (7 for
    // secondary, 30+ for primary).
    function colorForIndex(i) {
        var hue = (i * 137.508) % 360;
        return "hsl(" + hue.toFixed(0) + ", 62%, 42%)";
    }

    var map = L.map(el);
    CODMap.tiles(map);

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

    var group = [];
    if (legendEl) legendEl.textContent = "";

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

        if (legendEl) {
            legendEl.appendChild(legendItem(color, p.name || "School"));
            legendEl.appendChild(document.createTextNode(" "));
        }
    });

    function popupHtml(p) {
        var o = ofsted[p.name];
        var name = escapeHtml(p.name || "School");
        var ofstedUrl = o ? safeUrl(o.url) : null;
        var html = "<strong>" + (ofstedUrl ? '<a href="' + escapeHtml(ofstedUrl) + '">' + name + "</a>" : name) + "</strong>";
        if (p.type) html += "<br>" + escapeHtml(p.type);
        if (p.address) html += "<br>" + escapeHtml(p.address);
        if (o && o.outcome) html += "<br>Ofsted: " + escapeHtml(o.outcome) + " (" + escapeHtml(o.date) + ")";
        if (ofstedUrl) html += '<br><a href="' + escapeHtml(ofstedUrl) + '">Ofsted inspection history</a>';
        var link = safeUrl(p.website || p.urn_url);
        if (link) {
            html +=
                '<br><a href="' +
                escapeHtml(link) +
                '" target="_blank" rel="noopener">School site ↗</a>';
        }
        html += '<br><small>Nearest by straight-line distance only</small>';
        return html;
    }

    if (group.length) {
        map.fitBounds(L.featureGroup(group).getBounds().pad(0.1));
    }
})();
