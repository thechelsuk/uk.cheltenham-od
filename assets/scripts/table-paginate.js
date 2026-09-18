// Client-side pagination for any <table data-paginate="30">. Works with
// table-sort.js (sorting re-orders the rows, which sends us back to page 1) and
// with filters that set `hidden` on rows (hidden rows aren't counted).
(function () {
    function paginate(table, size) {
        var body = table.querySelector("tbody");
        if (!body) return;

        var page = 1;
        var nav = document.createElement("nav");
        nav.className = "table-pagination";
        nav.setAttribute("aria-label", "Table pages");
        nav.hidden = true;

        var prev = document.createElement("button");
        prev.type = "button";
        prev.textContent = "← Previous";
        var next = document.createElement("button");
        next.type = "button";
        next.textContent = "Next →";
        var status = document.createElement("span");
        status.className = "table-pagination-status";
        status.setAttribute("aria-live", "polite");

        nav.appendChild(prev);
        nav.appendChild(status);
        nav.appendChild(next);
        var anchor = table.closest(".table-scroll") || table;
        anchor.parentNode.insertBefore(nav, anchor.nextSibling);

        function render() {
            var rows = Array.prototype.filter.call(body.rows, function (row) {
                return !row.hidden;
            });
            var pages = Math.max(1, Math.ceil(rows.length / size));
            page = Math.min(Math.max(page, 1), pages);
            var first = (page - 1) * size;
            rows.forEach(function (row, index) {
                row.classList.toggle("paged-out", index < first || index >= first + size);
            });
            nav.hidden = pages <= 1;
            prev.disabled = page <= 1;
            next.disabled = page >= pages;
            status.textContent =
                "Showing " + (rows.length ? first + 1 : 0) + "–" + Math.min(first + size, rows.length) +
                " of " + rows.length + " (page " + page + " of " + pages + ")";
        }

        function go(delta) {
            page += delta;
            render();
            anchor.scrollIntoView({ block: "nearest" });
        }

        prev.addEventListener("click", function () { go(-1); });
        next.addEventListener("click", function () { go(1); });

        // Row order changing means the table was re-sorted: start again at page 1.
        var pending = false;
        new MutationObserver(function () {
            if (pending) return;
            pending = true;
            setTimeout(function () {
                pending = false;
                page = 1;
                render();
            }, 0);
        }).observe(body, { childList: true });

        render();
    }

    document.addEventListener("DOMContentLoaded", function () {
        document.querySelectorAll("table[data-paginate]").forEach(function (table) {
            var size = parseInt(table.getAttribute("data-paginate"), 10);
            paginate(table, size > 0 ? size : 30);
        });
    });
})();
