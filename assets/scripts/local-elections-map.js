(function () {
    var el = document.getElementById("elections-map");
    var wardsEl = document.getElementById("elections-map-wards");
    var summaryEl = document.getElementById("elections-map-summary");
    if (!el || !wardsEl || !summaryEl || typeof L === "undefined") return;

    var wards = [];
    var summary = [];
    try {
        wards = JSON.parse(wardsEl.textContent) || [];
        summary = JSON.parse(summaryEl.textContent) || [];
    } catch (e) {
        return;
    }
    if (!wards.length) return;

    function escapeHtml(text) {
        var div = document.createElement("div");
        div.textContent = text == null ? "" : text;
        return div.innerHTML;
    }

    var colours = {
        "Liberal Democrat": "#f59e0b",
        "Green": "#16a34a",
        "Reform UK": "#0ea5e9",
        "Conservative": "#2563eb",
        "Labour": "#dc2626",
        "People Against Bureaucracy": "#7c3aed",
        "Independent": "#64748b",
        "Split": "#94a3b8",
    };
    function colourOf(party) {
        return colours[party] || "#475569";
    }

    var bySlug = {};
    summary.forEach(function (row) {
        bySlug[row.slug] = row;
    });

    var map = L.map(el, { zoomSnap: 0.25 });
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);

    var used = {};
    var group = L.featureGroup().addTo(map);
    wards.forEach(function (w) {
        var row = bySlug[w.slug] || { party: "Split", councillors: [] };
        used[row.party] = true;
        var people = row.councillors
            .map(function (c) {
                return escapeHtml(c.name) + " (" + escapeHtml(c.party) + ")";
            })
            .join("<br>");
        var poly = L.polygon(w.boundary, {
            color: "#334155",
            weight: 2,
            fillColor: colourOf(row.party),
            fillOpacity: 0.7,
        });
        poly.bindPopup(
            "<strong>" + escapeHtml(w.name) + "</strong><br>" + people +
            '<br><a href="/cheltenham-wards/' + encodeURIComponent(w.slug) + '">View ' + escapeHtml(w.name) + " &rarr;</a>"
        );
        poly.bindTooltip(escapeHtml(w.name), { sticky: true });
        poly.addTo(group);
    });

    var legend = document.getElementById("elections-legend");
    if (legend) {
        legend.innerHTML = Object.keys(used)
            .sort()
            .map(function (party) {
                var label = party === "Split" ? "Split between parties" : escapeHtml(party);
                return '<span><i class="tier-swatch" style="background:' + colourOf(party) + '"></i> ' + label + "</span>";
            })
            .join("");
    }

    map.fitBounds(group.getBounds().pad(0.03));
})();
