(function () {
    var el = document.getElementById("where-to-eat-map");
    var dataEl = document.getElementById("where-to-eat-data");
    var typesEl = document.getElementById("where-to-eat-types");
    if (!el || !dataEl || typeof L === "undefined") return;

    var venues = [];
    var types = [];
    try {
        venues = JSON.parse(dataEl.textContent) || [];
        types = typesEl ? JSON.parse(typesEl.textContent) || [] : [];
    } catch (e) {
        return;
    }
    if (!venues.length) return;

    var labels = {};
    types.forEach(function (t) { labels[t.type] = t.label; });

    function colours(rating) {
        if (rating === "5") return ["#1e6e43", "#2e8b57"];
        if (rating === "4") return ["#5d8a1f", "#8bc34a"];
        if (rating === "3") return ["#b9770e", "#f39c12"];
        if (rating === "0" || rating === "1" || rating === "2") return ["#922b21", "#c0392b"];
        return ["#566573", "#7f8c8d"];
    }

    function ratingText(v) {
        if (v.rating === "AwaitingInspection") return "Awaiting inspection";
        if (v.rating === "") return "No rating recorded";
        return "Hygiene rating " + v.rating + " out of 5";
    }

    function escapeHtml(text) {
        var div = document.createElement("div");
        div.textContent = text;
        return div.innerHTML;
    }

    var map = L.map(el);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);

    var groups = {};
    var bounds = [];
    venues.forEach(function (v) {
        if (v.latitude == null || v.longitude == null) return;
        var c = colours(v.rating);
        var html = "<strong>" + escapeHtml(v.name) + "</strong><br>" + escapeHtml(labels[v.type] || v.type) +
            "<br>" + ratingText(v) +
            (v.rating_date ? "<br>Inspected " + v.rating_date : "") +
            "<br>" + escapeHtml(v.address) + (v.postcode ? ", " + escapeHtml(v.postcode) : "") +
            '<br><a href="https://ratings.food.gov.uk/business/' + v.id + '">Official rating record</a>';
        var marker = L.circleMarker([v.latitude, v.longitude], { radius: 7, color: c[0], fillColor: c[1], fillOpacity: 0.85, weight: 2 })
            .bindPopup(html);
        (groups[v.type] = groups[v.type] || L.layerGroup()).addLayer(marker);
        bounds.push([v.latitude, v.longitude]);
    });
    Object.keys(groups).forEach(function (t) { groups[t].addTo(map); });
    if (bounds.length) map.fitBounds(bounds, { padding: [30, 30] });

    document.querySelectorAll(".where-to-eat-type").forEach(function (box) {
        box.addEventListener("change", function () {
            var type = box.value;
            if (groups[type]) {
                if (box.checked) groups[type].addTo(map);
                else map.removeLayer(groups[type]);
            }
            document.querySelectorAll('#where-to-eat-table tbody tr[data-type="' + type + '"]').forEach(function (row) {
                row.style.display = box.checked ? "" : "none";
            });
        });
    });
})();
