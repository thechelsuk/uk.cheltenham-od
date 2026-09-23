// Site-wide Chart.js defaults, loaded straight after Chart.js by
// _includes/chartjs.html so every chart shares one look:
// - text, gridlines and font come from the site's CSS variables and follow
//   the light/dark theme toggle;
// - charts fill their .chart-canvas wrapper (400px) instead of keeping an
//   aspect ratio, which left them a few pixels tall on phones;
// - series without their own colour get one from a fixed, colour-blind-safe
//   palette. Places always keep the same colour (Cheltenham is always the
//   first slot), and other series take the remaining slots in order.
(function () {
    if (typeof Chart === "undefined") return;

    var root = document.documentElement;

    // The same eight hues stepped separately for each theme, checked for
    // colour-blind separation against the site's light and dark backgrounds.
    var PALETTE = {
        light: ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"],
        dark: ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"],
    };

    // Areas compared across several pages keep their slot everywhere.
    var PLACES = {
        "Cheltenham": 0,
        "Cheltenham residents": 0,
        "South West": 1,
        "England": 2,
        "Gloucestershire": 3,
    };

    function isDark() {
        return root.getAttribute("data-theme") === "dark";
    }

    function cssVar(name, fallback) {
        var value = getComputedStyle(root).getPropertyValue(name).trim();
        return value || fallback;
    }

    function applyTheme() {
        Chart.defaults.color = cssVar("--text-secondary", "#52514c");
        Chart.defaults.borderColor = cssVar("--border", "#dcdad2");
        Chart.defaults.font.family = cssVar("--font-sans", "sans-serif");
    }

    function withAlpha(hex, alpha) {
        var n = parseInt(hex.slice(1), 16);
        return "rgba(" + (n >> 16) + ", " + ((n >> 8) & 255) + ", " + (n & 255) + ", " + alpha + ")";
    }

    // Hands out palette slots: places first, then everything else in order,
    // skipping any slot a place on the same chart already holds.
    function slotsFor(datasets) {
        var taken = {};
        datasets.forEach(function (ds) {
            if (ds.label in PLACES) taken[PLACES[ds.label]] = true;
        });
        var next = 0;
        return datasets.map(function (ds) {
            if (ds.label in PLACES) return PLACES[ds.label];
            while (taken[next]) next++;
            taken[next] = true;
            return next++ % PALETTE.light.length;
        });
    }

    var palettePlugin = {
        id: "sitePalette",
        beforeUpdate: function (chart) {
            var colours = PALETTE[isDark() ? "dark" : "light"];
            var datasets = chart.data.datasets;
            var slots = slotsFor(datasets);
            datasets.forEach(function (ds, i) {
                // Leave colours a chart chose itself (e.g. collision severity).
                if (ds.borderColor !== undefined && !ds._sitePalette) return;
                if (ds.backgroundColor !== undefined && !ds._sitePalette) return;
                var colour = colours[slots[i]];
                var type = ds.type || chart.config.type;
                ds._sitePalette = true;
                ds.borderColor = colour;
                ds.backgroundColor = type === "line" && ds.fill ? withAlpha(colour, 0.12) : colour;
                ds.pointBackgroundColor = colour;
            });
        },
    };

    Chart.register(palettePlugin);
    Chart.defaults.plugins.colors = { enabled: false };
    Chart.defaults.maintainAspectRatio = false;
    Chart.defaults.plugins.legend.labels.boxWidth = 12;
    Chart.defaults.plugins.legend.labels.boxHeight = 12;
    applyTheme();

    // Chart.js copies the default axis colours into each chart when it is
    // created, so a theme change has to write the new ones into every axis.
    function recolour(chart) {
        var scales = chart.config.options.scales || {};
        Object.keys(chart.scales).forEach(function (id) {
            var scale = scales[id] || (scales[id] = {});
            ["ticks", "grid", "border", "title"].forEach(function (part) {
                scale[part] = scale[part] || {};
            });
            scale.ticks.color = Chart.defaults.color;
            scale.title.color = Chart.defaults.color;
            scale.grid.color = Chart.defaults.borderColor;
            scale.border.color = Chart.defaults.borderColor;
        });
        chart.update("none");
    }

    // Redraw every chart when the theme toggle flips data-theme.
    new MutationObserver(function () {
        applyTheme();
        Object.values(Chart.instances).forEach(recolour);
    }).observe(root, { attributes: true, attributeFilter: ["data-theme"] });
})();
