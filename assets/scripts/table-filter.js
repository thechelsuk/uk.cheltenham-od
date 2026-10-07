// Filters a data table by one or more of its columns, set in the page's front matter:
//
//   filters:
//     - table: 1        # which data table on the page, counting from 1
//       column: Type    # the column heading to filter on
//       style: buttons  # optional: "buttons" or "dropdown" to override
//
// The options are the distinct values in that column. Up to four short
// options become buttons; anything else becomes a dropdown, unless the
// page sets a style. Several filters on the same table share one bar and
// combine, so a row shows only when it matches every one. Without
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
    var groups = new Map();

    function cellText(row, index) {
        var cell = row.cells[index];
        return cell ? cell.textContent.replace(/\s+/g, " ").trim() : "";
    }

    // One bar per table, holding every filter set on it.
    function groupFor(table) {
        if (groups.has(table)) return groups.get(table);

        var bar = document.createElement("div");
        bar.className = "filter-bar";
        bar.setAttribute("role", "group");

        var count = document.createElement("span");
        count.className = "filter-count";
        count.setAttribute("aria-live", "polite");

        var clear = document.createElement("button");
        clear.type = "button";
        clear.className = "filter-clear";
        clear.textContent = "Clear";
        clear.classList.add("is-idle");

        var group = {
            bar: bar,
            count: count,
            clear: clear,
            rows: Array.from(table.tBodies[0].rows),
            controls: [],
        };

        group.refresh = function () {
            var shown = 0;
            group.rows.forEach(function (row) {
                var match = group.controls.every(function (control) {
                    return (
                        !control.value ||
                        cellText(row, control.column) === control.value
                    );
                });
                row.hidden = !match;
                if (match) shown++;
            });
            count.textContent =
                "Showing " +
                shown.toLocaleString("en-GB") +
                " of " +
                group.rows.length.toLocaleString("en-GB");
            clear.classList.toggle(
                "is-idle",
                group.controls.every(function (control) {
                    return !control.value;
                }),
            );
            group.controls.forEach(function (control) {
                control.show();
            });
        };

        clear.addEventListener("click", function () {
            group.controls.forEach(function (control) {
                control.value = "";
            });
            group.refresh();
        });

        bar.appendChild(clear);
        bar.appendChild(count);
        var anchor = table.closest(".table-scroll") || table;
        anchor.parentNode.insertBefore(bar, anchor);
        groups.set(table, group);
        return group;
    }

    filters.forEach(function (filter, filterIndex) {
        var table = tables[(filter.table || 1) - 1];
        if (!table || !table.tHead || !table.tBodies[0]) return;

        var wanted = String(filter.column || "").toLowerCase();
        var headers = Array.from(table.tHead.rows[0].cells);
        var column = headers.findIndex(function (th) {
            return (
                th.textContent.replace(/\s+/g, " ").trim().toLowerCase() ===
                wanted
            );
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
            return a.localeCompare(b, undefined, {
                numeric: true,
                sensitivity: "base",
            });
        });
        if (values.length < 2) return;

        var group = groupFor(table);
        var label = filter.label || headers[column].textContent.trim();
        var id = "table-filter-" + filterIndex;
        var control = { column: column, value: "", show: function () {} };
        var parts = [];

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
            var buttonGroup = document.createElement("div");
            buttonGroup.className = "filter-buttons";
            buttonGroup.setAttribute("role", "group");
            buttonGroup.setAttribute("aria-label", "Filter by " + label);
            var buttons = [""].concat(values).map(function (value) {
                var button = document.createElement("button");
                button.type = "button";
                button.dataset.value = value;
                button.textContent = value || "All";
                button.addEventListener("click", function () {
                    control.value = value;
                    group.refresh();
                });
                buttonGroup.appendChild(button);
                return button;
            });
            control.show = function () {
                buttons.forEach(function (button) {
                    button.setAttribute(
                        "aria-pressed",
                        String(button.dataset.value === control.value),
                    );
                });
            };
            parts.push(caption, buttonGroup);
        } else {
            var labelEl = document.createElement("label");
            labelEl.className = "filter-label";
            labelEl.htmlFor = id;
            labelEl.textContent = label;
            var select = document.createElement("select");
            select.id = id;
            [""].concat(values).forEach(function (value) {
                var option = document.createElement("option");
                option.value = value;
                option.textContent = value || "All";
                select.appendChild(option);
            });
            select.addEventListener("change", function () {
                control.value = select.value;
                group.refresh();
            });
            control.show = function () {
                select.value = control.value;
            };
            parts.push(labelEl, select);
        }

        parts.forEach(function (part) {
            group.bar.insertBefore(part, group.clear);
        });
        group.controls.push(control);
        group.bar.setAttribute(
            "aria-label",
            "Filter by " +
                group.controls
                    .map(function (c) {
                        return headers[c.column].textContent.trim();
                    })
                    .join(" and "),
        );
        group.refresh();
    });
})();
