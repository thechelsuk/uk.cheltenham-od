(function () {
    var select = document.getElementById("charity-cause");
    var search = document.getElementById("charity-search");
    var table = document.querySelector(".charities-list");
    if (!select || !search || !table) return;

    var rows = table.querySelectorAll("tbody tr[data-causes]");

    function apply() {
        var cause = select.value;
        var text = search.value.trim().toLowerCase();
        rows.forEach(function (row) {
            var causes = row.getAttribute("data-causes").split("|");
            var matchesCause = !cause || causes.indexOf(cause) !== -1;
            var matchesText = !text || row.textContent.toLowerCase().indexOf(text) !== -1;
            row.hidden = !(matchesCause && matchesText);
        });
    }

    select.addEventListener("change", apply);
    search.addEventListener("input", apply);
})();
