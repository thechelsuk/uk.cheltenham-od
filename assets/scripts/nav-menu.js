document.addEventListener("DOMContentLoaded", function () {
    var btn = document.getElementById("nav-toggle-btn");
    var panel = document.getElementById("nav-panel");
    if (!btn || !panel) return;

    function closePanel() {
        panel.hidden = true;
        btn.setAttribute("aria-expanded", "false");
    }

    function openPanel() {
        panel.hidden = false;
        btn.setAttribute("aria-expanded", "true");
    }

    btn.addEventListener("click", function () {
        if (panel.hidden) {
            openPanel();
        } else {
            closePanel();
        }
    });

    document.addEventListener("keydown", function (e) {
        if (e.key === "Escape" && !panel.hidden) {
            closePanel();
            btn.focus();
        }
    });

    document.addEventListener("click", function (e) {
        var clickedInsidePanel = panel.contains(e.target);
        var clickedToggle = btn.contains(e.target);
        if (!panel.hidden && !clickedInsidePanel && !clickedToggle) {
            closePanel();
        }
    });
});
