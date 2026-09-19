(function () {
    var STALE_AFTER_MINUTES = 45;

    var board = document.getElementById("rail-times");
    var notice = document.getElementById("rail-times-stale");
    if (!board || !notice) return;

    var generated = new Date(board.dataset.generated);
    if (isNaN(generated)) return;

    var minutes = Math.round((Date.now() - generated.getTime()) / 60000);
    if (minutes < STALE_AFTER_MINUTES) return;

    var age;
    if (minutes < 120) {
        age = minutes + " minutes";
    } else if (minutes < 2880) {
        age = Math.round(minutes / 60) + " hours";
    } else {
        age = Math.round(minutes / 1440) + " days";
    }

    notice.querySelector("span").textContent = age;
    notice.hidden = false;
})();
