(function () {
    var select = document.getElementById("grade-filter");
    var table = document.querySelector(".listed-buildings-table");
    if (!select || !table) return;

    var rows = table.querySelectorAll("tbody tr[data-grade]");

    select.addEventListener("change", function () {
        var grade = select.value;
        rows.forEach(function (row) {
            row.hidden = Boolean(grade) && row.getAttribute("data-grade") !== grade;
        });
    });
})();
