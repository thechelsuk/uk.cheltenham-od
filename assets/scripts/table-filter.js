// Filters a data table by one of its columns, set in the page's front matter:
//
//   filters:
//     - table: 1        # which data table on the page, counting from 1
//       column: Type    # the column heading to filter on
//       style: buttons  # optional: "buttons" or "dropdown" to override
//
// The options are the distinct values in that column. Up to four short
// options become buttons; anything else becomes a dropdown, unless the
// page sets a style. Without
// JavaScript the full table still shows and sorts.
(function () {
    var config = document.getElementById("table-filters");
    if (!config) return;

    var filters;
    try {
        filters = JSON.parse(config.textContent) || [];
    } catch (e) {
        return;
    }

    var MAX_BUTTONS = 4;
    var MAX_BUTTON_LABEL = 16;
    var tables = document.querySelectorAll("table.data-table");

    function cellText(row, index) {
        var cell = row.cells[index];
        return cell ? cell.textContent.replace(/\s+/g, " ").trim() : "";
    }

    filters.forEach(function (filter, filterIndex) {
        var table = tables[(filter.table || 1) - 1];
        if (!table || !table.tHead || !table.tBodies[0]) return;

        var wanted = String(filter.column || "").toLowerCase();
        var headers = Array.from(table.tHead.rows[0].cells);
        var column = headers.findIndex(function (th) {
            return th.textContent.replace(/\s+/g, " ").trim().toLowerCase() === wanted;
        });
        if (column < 0) return;

        var rows = Array.from(table.tBodies[0].rows);
        var values = Array.from(
            new Set(
                rows
                    .map(function (row) {
                        return cellText(row, column);
                    })
                    .filter(Boolean),
            ),
        ).sort(function (a, b) {
            return a.localeCompare(b, undefined, { numeric: true, sensitivity: "base" });
        });
        if (values.length < 2) return;

        var label = filter.label || headers[column].textContent.trim();
        var id = "table-filter-" + filterIndex;
        var bar = document.createElement("div");
        bar.className = "filter-bar";
        bar.setAttribute("role", "group");
        bar.setAttribute("aria-label", "Filter by " + label);

        var count = document.createElement("span");
        count.className = "filter-count";
        count.setAttribute("aria-live", "polite");

        var clear = document.createElement("button");
        clear.type = "button";
        clear.className = "filter-clear";
        clear.textContent = "Clear";
        clear.classList.add("is-idle");

        var current = "";
        var select = null;
        var buttons = [];

        function apply(value) {
            current = value;
            var shown = 0;
            rows.forEach(function (row) {
                var match = !value || cellText(row, column) === value;
                row.hidden = !match;
                if (match) shown++;
            });
            count.textContent = "Showing " + shown.toLocaleString("en-GB") + " of " + rows.length.toLocaleString("en-GB");
            clear.classList.toggle("is-idle", !value);
            if (select) select.value = value;
            buttons.forEach(function (button) {
                button.setAttribute("aria-pressed", String(button.dataset.value === value));
            });
        }

        var longest = Math.max.apply(
            null,
            values.map(function (v) {
                return v.length;
            }),
        );
        var useButtons = filter.style
            ? filter.style === "buttons"
            : values.length <= MAX_BUTTONS && longest <= MAX_BUTTON_LABEL;

        if (useButtons) {
            var caption = document.createElement("span");
            caption.className = "filter-label";
            caption.textContent = label;
            var group = document.createElement("div");
            group.className = "filter-buttons";
            [""].concat(values).forEach(function (value) {
                var button = document.createElement("button");
                button.type = "button";
                button.dataset.value = value;
                button.textContent = value || "All";
                button.addEventListener("click", function () {
                    apply(value);
                });
                buttons.push(button);
                group.appendChild(button);
            });
            bar.appendChild(caption);
            bar.appendChild(group);
        } else {
            var labelEl = document.createElement("label");
            labelEl.className = "filter-label";
            labelEl.htmlFor = id;
            labelEl.textContent = label;
            select = document.createElement("select");
            select.id = id;
            var all = document.createElement("option");
            all.value = "";
            all.textContent = "All";
            select.appendChild(all);
            values.forEach(function (value) {
                var option = document.createElement("option");
                option.value = value;
                option.textContent = value;
                select.appendChild(option);
            });
            select.addEventListener("change", function () {
                apply(select.value);
            });
            bar.appendChild(labelEl);
            bar.appendChild(select);
        }

        clear.addEventListener("click", function () {
            apply("");
        });
        bar.appendChild(clear);
        bar.appendChild(count);

        var anchor = table.closest(".table-scroll") || table;
        anchor.parentNode.insertBefore(bar, anchor);
        apply(current);
    });
})();
