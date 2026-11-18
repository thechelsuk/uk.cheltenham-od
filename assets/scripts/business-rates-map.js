// Business rates maps for /cheltenham-business-rates (one circle per
// postcode, data-mode="postcodes") and its empty properties page (one circle
// per empty property, data-mode="empty"). Circles use the same six blues as
// the other shaded maps, darker for a higher rateable value band; the bands
// are also named in the legend, the filter and every popup, so nothing
// depends on telling the shades apart.
(function () {
    var el = document.getElementById("business-rates-map");
    var dataEl = document.getElementById("business-rates-map-data");
    if (!el || !dataEl || typeof L === "undefined") return;

    var data;
    try {
        data = JSON.parse(dataEl.textContent);
    } catch (e) {
        return;
    }
    if (!data || !data.bands) return;

    var mode = el.getAttribute("data-mode") === "empty" ? "empty" : "postcodes";
    var bandEl = document.getElementById("business-rates-map-band");
    var statusEl = document.getElementById("business-rates-map-status");
    var legend = document.getElementById("business-rates-map-legend");
    var shades = [
        "#eff3ff",
        "#c6dbef",
        "#9ecae1",
        "#6baed6",
        "#3182bd",
        "#08519c",
    ];
    var awaiting = "#ffffff";

    function escapeHtml(text) {
        var div = document.createElement("div");
        div.textContent = text == null ? "" : text;
        return div.innerHTML;
    }

    function money(n) {
        return "£" + Number(n).toLocaleString("en-GB");
    }

    function bandOf(rv) {
        if (!rv) return null;
        for (var i = 0; i < data.upper.length; i++) {
            if (rv <= data.upper[i]) return i;
        }
        return data.upper.length;
    }

    function bandName(band) {
        return band == null ? "Awaiting a rateable value" : data.bands[band];
    }

    if (legend) {
        var html = "";
        data.bands.forEach(function (label, i) {
            html +=
                '<span><i class="tier-swatch shade-' +
                i +
                '"></i> ' +
                escapeHtml(label) +
                "</span>";
        });
        html +=
            '<span><i class="tier-swatch" style="background: ' +
            awaiting +
            '"></i> Awaiting a rateable value</span>';
        legend.innerHTML = html;
    }

    var points = (mode === "empty" ? data.empty : data.postcodes).filter(
        function (p) {
            return p.lat != null && p.lon != null;
        },
    );
    if (!points.length) return;

    var map = L.map(el, { zoomSnap: 0.25 });
    CODMap.tiles(map);
    map.fitBounds(
        L.latLngBounds(
            points.map(function (p) {
                return [p.lat, p.lon];
            }),
        ).pad(0.03),
    );
    var group = L.featureGroup().addTo(map);

    function circle(lat, lon, band, html) {
        var fill = band == null ? awaiting : shades[band];
        return L.circleMarker([lat, lon], {
            radius: 6,
            color: "#334155",
            weight: 1,
            fillColor: fill,
            fillOpacity: 0.85,
        }).bindPopup(html);
    }

    function wanted(band) {
        var chosen = bandEl ? bandEl.value : "all";
        if (chosen === "all") return true;
        if (chosen === "awaiting") return band == null;
        return band === Number(chosen);
    }

    function drawPostcodes() {
        var onlyEmpty = statusEl && statusEl.value === "empty";
        data.postcodes.forEach(function (pc) {
            var props = pc.p.filter(function (p) {
                return wanted(bandOf(p[0])) && (!onlyEmpty || p[2] != null);
            });
            if (!props.length) return;
            var empty = props.filter(function (p) {
                return p[2] != null;
            }).length;
            var values = props
                .map(function (p) {
                    return p[0];
                })
                .filter(Boolean)
                .sort(function (a, b) {
                    return a - b;
                });
            var top = values.length ? values[values.length - 1] : 0;
            var html =
                "<strong>" +
                escapeHtml(pc.postcode) +
                "</strong><br>" +
                props.length +
                (props.length === 1 ? " property" : " properties") +
                ": " +
                (props.length - empty) +
                " occupied, " +
                empty +
                " empty";
            if (values.length) {
                html +=
                    "<br>Rateable value: " +
                    (values.length === 1 || values[0] === top
                        ? money(top)
                        : money(values[0]) + " to " + money(top));
                html +=
                    "<br>Highest band: " + escapeHtml(bandName(bandOf(top)));
            }
            var types = {};
            props.forEach(function (p) {
                var t = data.types[p[1]];
                types[t] = (types[t] || 0) + 1;
            });
            html +=
                "<br>" +
                Object.keys(types)
                    .sort(function (a, b) {
                        return types[b] - types[a];
                    })
                    .slice(0, 4)
                    .map(function (t) {
                        return escapeHtml(t) + ": " + types[t];
                    })
                    .join("<br>");
            circle(pc.lat, pc.lon, bandOf(top), html).addTo(group);
        });
    }

    function drawEmpty() {
        data.empty.forEach(function (e) {
            if (e.lat == null || e.lon == null || !wanted(e.band)) return;
            var html =
                "<strong>" +
                escapeHtml(e.address) +
                "</strong><br>" +
                escapeHtml(e.postcode) +
                "<br>" +
                escapeHtml(e.type) +
                "<br>Rateable value: " +
                escapeHtml(e.rv_display) +
                " (" +
                escapeHtml(bandName(e.band)) +
                ")<br>Start date: " +
                escapeHtml(e.since || "Not stated") +
                "<br>Empty in " +
                e.releases_empty +
                " of " +
                data.release_count +
                " lists<br>Exemption: " +
                escapeHtml(e.reason);
            circle(e.lat, e.lon, e.band, html).addTo(group);
        });
    }

    function render() {
        group.clearLayers();
        map.closePopup();
        if (mode === "empty") drawEmpty();
        else drawPostcodes();
    }

    if (bandEl) bandEl.addEventListener("change", render);
    if (statusEl) statusEl.addEventListener("change", render);
    render();
})();
