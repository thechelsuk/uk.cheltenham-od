(function () {
    var el = document.getElementById("renewable-map-data");
    var mapEl = document.getElementById("renewable-map");
    if (!el || !mapEl || typeof L === "undefined") return;

    var sites;
    try {
        sites = JSON.parse(el.textContent) || [];
    } catch (e) {
        return;
    }
    var statusEl = document.getElementById("renewable-map-status");

    function escapeHtml(text) {
        var div = document.createElement("div");
        div.textContent = text == null ? "" : text;
        return div.innerHTML;
    }

    function popupFor(s) {
        var html = "<strong>" + escapeHtml(s.name) + "</strong>";
        html += "<br>" + escapeHtml(s.technology);
        if (s.capacity_mw != null) html += ", " + s.capacity_mw + " MW";
        html += "<br>Status: " + escapeHtml(s.status_detail || s.status);
        if (s.operational) html += "<br>Operational: " + escapeHtml(s.operational);
        html += "<br>" + escapeHtml(s.council) + " council";
        if (s.planning_ref) html += "<br>Planning reference: " + escapeHtml(s.planning_ref);
        if (s.operator) html += "<br>Operator: " + escapeHtml(s.operator);
        if (s.updated) html += "<br>Updated: " + escapeHtml(s.updated);
        html += "<br>" + s.miles + " miles from the town centre";
        return html;
    }

    var map = L.map(mapEl);
    CODMap.tiles(map);

    var group = L.featureGroup().addTo(map);
    var markers = sites.map(function (s) {
        var m = L.marker([s.lat, s.lng]).bindPopup(popupFor(s));
        m.status = s.status;
        return m;
    });

    function render() {
        var wanted = statusEl ? statusEl.value : "";
        group.clearLayers();
        markers.forEach(function (m) {
            if (!wanted || m.status === wanted) group.addLayer(m);
        });
        map.closePopup();
    }

    if (statusEl) statusEl.addEventListener("change", render);
    render();

    if (markers.length) {
        map.fitBounds(L.featureGroup(markers).getBounds().pad(0.05));
    } else {
        map.setView([51.9, -2.08], 11);
    }

    // Table pins show their project, switching the status filter back to all
    // projects first if the project is hidden.
    document.querySelectorAll("[data-map-pin]").forEach(function (pin) {
        pin.addEventListener(
            "click",
            function () {
                if (statusEl && statusEl.value) {
                    statusEl.value = "";
                    render();
                }
            },
            true,
        );
    });
    CODMap.linkPins(map, el);
})();
