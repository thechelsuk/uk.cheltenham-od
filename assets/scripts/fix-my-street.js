(function () {
    var table = document.querySelector(".fms-table");
    if (!table) return;

    var groupSelect = document.getElementById("fms-group-filter");
    var countEl = document.getElementById("fms-count");
    var rows = Array.prototype.slice.call(table.querySelectorAll("tbody tr[data-group]"));

    // Optional map (latest-reports page only). Rows and markers share an index.
    var mapEl = document.getElementById("fms-map");
    var dataEl = document.getElementById("fms-data");
    var items = [];
    var map = null;
    var markers = null;
    if (mapEl && dataEl && typeof L !== "undefined") {
        try {
            items = JSON.parse(dataEl.textContent) || [];
        } catch (e) {
            items = [];
        }
        map = L.map(mapEl);
        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
            maxZoom: 19,
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        }).addTo(map);
        markers = L.layerGroup().addTo(map);
    }

    function escapeHtml(text) {
        var div = document.createElement("div");
        div.textContent = text == null ? "" : String(text);
        return div.innerHTML;
    }

    function drawMarkers(visible) {
        if (!map) return;
        markers.clearLayers();
        var bounds = [];
        items.forEach(function (item) {
            if (item.lat == null || item.lon == null || !visible(item)) return;
            var html =
                "<strong>" + escapeHtml(item.title) + "</strong><br>" +
                escapeHtml(item.group) + "<br>" +
                '<a href="' + escapeHtml(item.url) + '" rel="noopener">View on FixMyStreet</a>';
            L.marker([item.lat, item.lon]).bindPopup(html).addTo(markers);
            bounds.push([item.lat, item.lon]);
        });
        // Cheltenham town centre when nothing matches the filters.
        if (bounds.length) map.fitBounds(bounds, { padding: [30, 30], maxZoom: 15 });
        else map.setView([51.897991, -2.071308], 12);
    }

    function apply() {
        var group = groupSelect ? groupSelect.value : "";
        var shown = 0;
        rows.forEach(function (row) {
            var hide = Boolean(group) && row.getAttribute("data-group") !== group;
            row.hidden = hide;
            if (!hide) shown += 1;
        });
        if (countEl) countEl.textContent = "Showing " + shown + " of " + rows.length;
        drawMarkers(function (item) {
            return !group || item.group === group;
        });
    }

    if (groupSelect) groupSelect.addEventListener("change", apply);
    apply();
})();
