(function () {
    function valueFor(cell) {
        return (
            cell.dataset.value ||
            cell.dataset.val ||
            cell.textContent ||
            ""
        ).trim();
    }

    function compareValues(left, right) {
        var leftValue = left.replace(/^-+$/, "");
        var rightValue = right.replace(/^-+$/, "");
        var numericPattern = /^[-+]?\d[\d,]*(?:\.\d+)?[a-zA-Z%/]*$/;
        var leftNumericValue = leftValue.replace(/[£$€\s]/g, "");
        var rightNumericValue = rightValue.replace(/[£$€\s]/g, "");
        var leftIsNumber = numericPattern.test(leftNumericValue);
        var rightIsNumber = numericPattern.test(rightNumericValue);
        var leftNumber = Number(
            leftNumericValue.replace(/,/g, "").replace(/[a-zA-Z%/]+$/, ""),
        );
        var rightNumber = Number(
            rightNumericValue.replace(/,/g, "").replace(/[a-zA-Z%/]+$/, ""),
        );

        if (leftIsNumber && rightIsNumber) return leftNumber - rightNumber;
        if (leftIsNumber) return -1;
        if (rightIsNumber) return 1;
        return leftValue.localeCompare(rightValue, undefined, {
            numeric: true,
            sensitivity: "base",
        });
    }

    function makeSortable(table) {
        var headers = Array.from(table.querySelectorAll("thead th"));
        var body = table.querySelector("tbody");
        if (!body || headers.length === 0) return;

        headers.forEach(function (header, index) {
            header.addEventListener("click", function () {
                var ascending = header.dataset.sortDirection !== "asc";
                var rows = Array.from(body.querySelectorAll("tr"));

                rows.sort(function (leftRow, rightRow) {
                    var left = valueFor(leftRow.cells[index]);
                    var right = valueFor(rightRow.cells[index]);
                    var result = compareValues(left, right);
                    return ascending ? result : -result;
                });

                rows.forEach(function (row) {
                    body.appendChild(row);
                });
                headers.forEach(function (item) {
                    delete item.dataset.sortDirection;
                    item.classList.remove("sort-asc", "sort-desc");
                });
                header.dataset.sortDirection = ascending ? "asc" : "desc";
                header.classList.add(ascending ? "sort-asc" : "sort-desc");
            });
        });
    }

    document.addEventListener("DOMContentLoaded", function () {
        document.querySelectorAll("table[data-sortable]").forEach(makeSortable);
    });
})();
