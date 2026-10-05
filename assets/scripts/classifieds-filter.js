// Shows one category of classified adverts at a time. The buttons are
// written by the classifieds layout; this reveals the bar and hides the
// other category sections. Without JavaScript every section shows.
(function () {
    var bar = document.getElementById("classifieds-filter");
    if (!bar) return;

    var buttons = bar.querySelectorAll(".filter-buttons button");
    var clear = bar.querySelector(".filter-clear");
    var count = bar.querySelector(".filter-count");
    var sections = document.querySelectorAll("section.classifieds-category");

    function apply(value) {
        var shown = 0;
        sections.forEach(function (section) {
            var match = !value || section.id === value;
            section.hidden = !match;
            if (match) shown += section.querySelectorAll(".classifieds-item").length;
        });
        buttons.forEach(function (button) {
            button.setAttribute("aria-pressed", String(button.dataset.value === value));
        });
        clear.classList.toggle("is-idle", !value);
        count.textContent = "Showing " + shown + " advert" + (shown === 1 ? "" : "s");
    }

    buttons.forEach(function (button) {
        button.addEventListener("click", function () {
            apply(button.dataset.value);
        });
    });
    clear.addEventListener("click", function () {
        apply("");
    });

    bar.hidden = false;
})();
