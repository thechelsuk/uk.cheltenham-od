(function () {
    var root = document.getElementById("where-to-eat-picker");
    var dataEl = document.getElementById("where-to-eat-data");
    var typesEl = document.getElementById("where-to-eat-types");
    var button = document.getElementById("where-to-eat-picker-button");
    var select = document.getElementById("where-to-eat-picker-type");
    var result = document.getElementById("where-to-eat-picker-result");
    if (!root || !dataEl || !button || !select || !result) return;

    var venues = [];
    var labels = {};
    try {
        venues = JSON.parse(dataEl.textContent) || [];
        (typesEl ? JSON.parse(typesEl.textContent) || [] : []).forEach(function (t) {
            labels[t.type] = t.label;
        });
    } catch (e) {
        return;
    }

    // Only well-rated venues are picked from. Anything else stays in the table and on the map.
    var pool = venues.filter(function (v) {
        return v.rating === "4" || v.rating === "5";
    });
    if (!pool.length) return;

    root.hidden = false;
    var last = null;

    function el(tag, className, text) {
        var node = document.createElement(tag);
        if (className) node.className = className;
        if (text != null) node.textContent = text;
        return node;
    }

    function actionLink(text, href) {
        var a = el("a", "latest-action-link", text);
        a.href = href;
        return a;
    }

    // Reuses the homepage weather card's styles for the result.
    function show(v) {
        var card = el("div", "weather-glance");
        card.appendChild(el("p", "weather-glance-date", labels[v.type] || v.type));

        var header = el("div", "weather-glance-header");
        var heading = el("div");
        heading.appendChild(el("span", "weather-glance-temp", v.name));
        heading.appendChild(el("span", "weather-glance-desc", v.address + (v.postcode ? ", " + v.postcode : "")));
        header.appendChild(heading);
        card.appendChild(header);

        var stats = el("ul", "weather-glance-stats");
        [["Hygiene rating", v.rating + " out of 5"], ["Inspected", v.rating_date || "Not recorded"]].forEach(function (row) {
            var li = el("li");
            li.appendChild(el("span", null, row[0]));
            li.appendChild(el("strong", null, row[1]));
            stats.appendChild(li);
        });
        card.appendChild(stats);

        var actions = el("p", "latest-actions");
        var record = actionLink("Official rating record", "https://ratings.food.gov.uk/business/" + v.id);
        record.target = "_blank";
        record.rel = "noopener";
        actions.appendChild(record);
        if (v.latitude != null && v.longitude != null) {
            var directions = actionLink("Directions", "https://www.google.com/maps/dir/?api=1&destination=" +
                v.latitude + "," + v.longitude);
            directions.target = "_blank";
            directions.rel = "noopener";
            actions.appendChild(directions);
            if (window.whereToEatMap) {
                var onMap = actionLink("Show on map", "#where-to-eat-map");
                onMap.addEventListener("click", function (event) {
                    event.preventDefault();
                    window.whereToEatMap.show(v.id);
                });
                actions.appendChild(onMap);
            }
        }
        card.appendChild(actions);
        card.appendChild(el("p", null, "Check opening hours before you go."));

        result.textContent = "";
        result.appendChild(card);
    }

    button.addEventListener("click", function () {
        var wanted = select.value;
        var candidates = pool.filter(function (v) {
            return !wanted || v.type === wanted;
        });
        if (!candidates.length) {
            result.textContent = "No places to pick from for that type.";
            return;
        }
        // Avoid repeating the last pick when there is a choice.
        var options = candidates.length > 1 ? candidates.filter(function (v) { return v.id !== last; }) : candidates;
        var pick = options[Math.floor(Math.random() * options.length)];
        last = pick.id;
        show(pick);
        button.textContent = "Pick another";
    });
})();
