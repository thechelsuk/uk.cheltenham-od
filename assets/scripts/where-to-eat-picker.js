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

    function line(text) {
        var p = document.createElement("p");
        p.textContent = text;
        return p;
    }

    function link(text, href) {
        var a = document.createElement("a");
        a.textContent = text;
        a.href = href;
        a.target = "_blank";
        a.rel = "noopener";
        return a;
    }

    function show(v) {
        result.textContent = "";
        var name = document.createElement("p");
        var strong = document.createElement("strong");
        strong.textContent = v.name;
        name.appendChild(strong);
        result.appendChild(name);
        result.appendChild(line((labels[v.type] || v.type) + ". Hygiene rating " + v.rating + " out of 5" +
            (v.rating_date ? ", inspected " + v.rating_date : "") + "."));
        result.appendChild(line(v.address + (v.postcode ? ", " + v.postcode : "")));

        var actions = document.createElement("p");
        actions.appendChild(link("Official rating record", "https://ratings.food.gov.uk/business/" + v.id));
        if (v.latitude != null && v.longitude != null) {
            actions.appendChild(document.createTextNode(" · "));
            actions.appendChild(link("Directions", "https://www.google.com/maps/dir/?api=1&destination=" +
                v.latitude + "," + v.longitude));
            if (window.whereToEatMap) {
                actions.appendChild(document.createTextNode(" · "));
                var showOnMap = document.createElement("button");
                showOnMap.type = "button";
                showOnMap.className = "where-to-eat-picker-map";
                showOnMap.textContent = "Show on map";
                showOnMap.addEventListener("click", function () {
                    window.whereToEatMap.show(v.id);
                });
                actions.appendChild(showOnMap);
            }
        }
        result.appendChild(actions);
        result.appendChild(line("Check opening hours before you go."));
    }

    button.addEventListener("click", function () {
        var wanted = select.value;
        var candidates = pool.filter(function (v) {
            return !wanted || v.type === wanted;
        });
        if (!candidates.length) {
            result.textContent = "";
            result.appendChild(line("No places to pick from for that type."));
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
