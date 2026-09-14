(function () {
    if (typeof Chart === "undefined") return;

    var dwellingsEl = document.getElementById("net-additional-dwellings-chart");
    var dwellingsDataEl = document.getElementById("net-additional-dwellings-data");
    if (dwellingsEl && dwellingsDataEl) {
        var years = [];
        try {
            years = JSON.parse(dwellingsDataEl.textContent) || [];
        } catch (e) {
            years = [];
        }
        if (years.length) {
            new Chart(dwellingsEl, {
                type: "bar",
                data: {
                    labels: years.map(function (y) { return y.year; }),
                    datasets: [
                        {
                            label: "Net additional dwellings",
                            data: years.map(function (y) { return y.net_additional_dwellings; }),
                        },
                    ],
                },
                options: {
                    responsive: true,
                    plugins: { legend: { display: false } },
                    scales: { y: { beginAtZero: true, ticks: { precision: 0 } } },
                },
            });
        }
    }

    var communalEl = document.getElementById("communal-accommodation-chart");
    var communalDataEl = document.getElementById("communal-accommodation-data");
    if (communalEl && communalDataEl) {
        var entries = [];
        try {
            entries = JSON.parse(communalDataEl.textContent) || [];
        } catch (e) {
            entries = [];
        }
        var bedspaces = entries.filter(function (e) { return e.metric === "bedspaces"; });
        if (bedspaces.length) {
            new Chart(communalEl, {
                type: "bar",
                data: {
                    labels: bedspaces.map(function (e) { return e.year; }),
                    datasets: [
                        {
                            label: "Student bedspaces (net change)",
                            data: bedspaces.map(function (e) { return e.student_net_change; }),
                        },
                        {
                            label: "Other bedspaces (net change)",
                            data: bedspaces.map(function (e) { return e.other_net_change; }),
                        },
                    ],
                },
                options: {
                    responsive: true,
                    scales: { y: { beginAtZero: true, ticks: { precision: 0 } } },
                },
            });
        }
    }
})();
