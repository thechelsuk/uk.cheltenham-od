(function () {
    var el = document.getElementById("planning-map");
    var dataEl = document.getElementById("planning-data");
    if (!el || !dataEl || typeof L === "undefined") return;

    var applications = [];
    try {
        applications = JSON.parse(dataEl.textContent) || [];
    } catch (e) {
        return;
    }

    function escapeHtml(text) {
        return String(text == null ? "" : text)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;");
    }

    function shorten(text, max) {
        text = String(text || "");
        if (text.length <= max) return text;
        return text.slice(0, max).replace(/\s+\S*$/, "") + "…";
    }

    // An application is in both lists once it has been decided, and every application in a postcode
    // sits on the same point, so group by reference first and then by location.
    var seen = {};
    var byPoint = {};
    applications.forEach(function (a) {
        if (a.lat == null || a.lon == null || seen[a.ref]) return;
        seen[a.ref] = true;
        var key = a.lat + "," + a.lon;
        (byPoint[key] = byPoint[key] || []).push(a);
    });

    var keys = Object.keys(byPoint);
    if (!keys.length) return;

    var map = L.map(el);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution:
            '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);

    var markers = keys.map(function (key) {
        var group = byPoint[key];
        var html = group
            .map(function (a) {
                var status = escapeHtml(a.status);
                if (a.url && a.url.indexOf("https://publicaccess.cheltenham.gov.uk/") === 0) {
                    status = '<a href="' + escapeHtml(a.url) + '" target="_blank" rel="noopener">' + status + "</a>";
                }
                var received = a.received_date ? "<br>Received " + escapeHtml(a.received_date) : "";
                return (
                    "<strong>" + escapeHtml(a.ref) + "</strong><br>" +
                    escapeHtml(a.address) + "<br>" +
                    escapeHtml(shorten(a.description, 140)) + received + "<br>" + status
                );
            })
            .join("<hr>");
        return L.marker([group[0].lat, group[0].lon]).bindPopup(html, { maxHeight: 260 });
    });

    var layer = L.featureGroup(markers).addTo(map);
    map.fitBounds(layer.getBounds().pad(0.15));
})();
