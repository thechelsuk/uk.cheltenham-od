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

    var bounds = [];
    venues.forEach(function (v) {
        if (v.latitude == null || v.longitude == null) return;
        var html = "<strong>" + escapeHtml(v.name) + "</strong><br>" + escapeHtml(labels[v.type] || v.type) +
            "<br>" + ratingText(v) +
            (v.rating_date ? "<br>Inspected " + v.rating_date : "") +
            "<br>" + escapeHtml(v.address) + (v.postcode ? ", " + escapeHtml(v.postcode) : "") +
            '<br><a href="https://ratings.food.gov.uk/business/' + v.id + '">Official rating record</a>';
        L.marker([v.latitude, v.longitude]).addTo(map).bindPopup(html);
        bounds.push([v.latitude, v.longitude]);
    });

    if (bounds.length) map.fitBounds(bounds, { padding: [30, 30] });
})();
