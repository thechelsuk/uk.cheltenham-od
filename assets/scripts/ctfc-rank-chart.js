// Cheltenham Town's rank among the 92 Premier League and Football League clubs
// each season, on the club's record page, with 1 at the top. The season in
// progress is a hollow point.
(function () {
    var el = document.getElementById("ctfc-rank-chart");
    var dataEl = document.getElementById("ctfc-rank-data");
    if (!el || !dataEl || typeof Chart === "undefined") return;

    var seasons = [];
    try {
        seasons = (JSON.parse(dataEl.textContent) || []).slice().reverse();
    } catch (e) {
        return;
    }
    if (!seasons.length) return;

    var BOTTOM = 95;

    function ordinal(n) {
        var tens = n % 100;
        if (tens >= 11 && tens <= 13) return n + "th";
        return n + ({ 1: "st", 2: "nd", 3: "rd" }[n % 10] || "th");
    }

    function outside(ctx) {
        var s = seasons[ctx.dataIndex];
        return s && s.rank_92 > 92;
    }

    function cssVar(name, fallback) {
        // Read from the canvas: the page theme sets the accent colour on <body>.
        var value = getComputedStyle(el).getPropertyValue(name).trim();
        return value || fallback;
    }

    new Chart(el, {
        type: "line",
        data: {
            labels: seasons.map(function (s) { return s.season_display; }),
            datasets: [
                {
                    label: "Cheltenham Town",
                    data: seasons.map(function (s) { return s.rank_92; }),
                    fill: false,
                    // A season outside the 92 is larger and in the site's accent colour.
                    pointRadius: function (ctx) {
                        return outside(ctx) ? 6 : 4;
                    },
                    pointHoverRadius: function (ctx) {
                        return outside(ctx) ? 8 : 6;
                    },
                    pointBorderWidth: 2,
                    pointBorderColor: function (ctx) {
                        return outside(ctx) ? cssVar("--accent", "#4a9d7a") : ctx.dataset.borderColor;
                    },
                    // The season in progress is hollow: filled with the page background.
                    pointBackgroundColor: function (ctx) {
                        var s = seasons[ctx.dataIndex];
                        if (outside(ctx)) return cssVar("--accent", "#4a9d7a");
                        return s && !s.complete ? cssVar("--bg", "#fff") : ctx.dataset.borderColor;
                    },
                },
            ],
        },
        options: {
            responsive: true,
            interaction: { mode: "index", intersect: false },
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        title: function (items) {
                            var s = seasons[items[0].dataIndex];
                            return s.season_display + ", " + s.division;
                        },
                        label: function (item) {
                            var s = seasons[item.dataIndex];
                            var lines = [
                                ordinal(s.position) + " of " + s.teams + (s.complete ? "" : " so far"),
                                s.rank_92 > 92 ? ordinal(s.rank_92) + ", outside the 92" : ordinal(s.rank_92) + " of the 92",
                                "Pld " + s.played + ", W " + s.won + ", D " + s.drawn + ", L " + s.lost,
                                "Pts " + s.points + ", PPG " + s.ppg_display,
                            ];
                            if (s.sorted_by === "points per game") lines.push("Table decided on points per game");
                            return lines;
                        },
                    },
                },
            },
            scales: {
                y: {
                    reverse: true,
                    min: 1,
                    max: BOTTOM,
                    // A gridline every 5 places, plus 1 at the top.
                    afterBuildTicks: function (axis) {
                        var ticks = [{ value: 1 }];
                        for (var v = 5; v <= BOTTOM; v += 5) ticks.push({ value: v });
                        axis.ticks = ticks;
                    },
                    title: { display: true, text: "Rank in the 92" },
                },
            },
        },
    });
})();
