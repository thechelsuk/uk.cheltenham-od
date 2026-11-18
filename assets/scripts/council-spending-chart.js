// Charts for the council spending pages: payments by month and by year on
// /cheltenham-council-spending, and net spending by service on
// /cheltenham-council-spending/accounts. Each reads its figures from a
// JSON script tag on the page and does nothing if its canvas is missing.
(function () {
    if (typeof Chart === "undefined") return;

    function read(id) {
        var el = document.getElementById(id);
        if (!el) return null;
        try {
            return JSON.parse(el.textContent);
        } catch (e) {
            return null;
        }
    }

    var monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

    function monthLabel(m) {
        return monthNames[parseInt(m.slice(5, 7), 10) - 1] + " " + m.slice(0, 4);
    }

    function pounds(v) {
        var sign = v < 0 ? "-" : "";
        var a = Math.abs(v);
        if (a >= 1000000) return sign + "£" + (a / 1000000).toFixed(1) + "m";
        if (a >= 1000) return sign + "£" + Math.round(a / 1000) + "k";
        return sign + "£" + Math.round(a);
    }

    function exact(v) {
        return (v < 0 ? "-£" : "£") + Math.round(Math.abs(v)).toLocaleString("en-GB");
    }

    function options(legend) {
        return {
            responsive: true,
            interaction: { mode: "index", intersect: false },
            plugins: {
                legend: { display: legend },
                tooltip: { callbacks: { label: function (ctx) { return ctx.dataset.label + ": " + exact(ctx.parsed.y); } } },
            },
            scales: { y: { ticks: { callback: function (v) { return pounds(v); } } } },
        };
    }

    var monthly = read("council-spending-monthly-data");
    var monthlyCanvas = document.getElementById("council-spending-monthly-chart");
    if (monthly && monthly.length && monthlyCanvas) {
        new Chart(monthlyCanvas, {
            type: "bar",
            data: {
                labels: monthly.map(function (m) { return monthLabel(m.month); }),
                datasets: [{ label: "Paid", data: monthly.map(function (m) { return m.payments; }) }],
            },
            options: options(false),
        });
    }

    var years = read("council-spending-yearly-data");
    var values = read("council-spending-yearly-values");
    var months = read("council-spending-yearly-months");
    var yearlyCanvas = document.getElementById("council-spending-yearly-chart");
    if (years && values && years.length && yearlyCanvas) {
        new Chart(yearlyCanvas, {
            type: "bar",
            data: {
                labels: years.map(function (y, i) {
                    return months && months[i] < 12 ? y + " (so far)" : y;
                }).reverse(),
                datasets: [{ label: "Paid", data: values.slice().reverse() }],
            },
            options: options(false),
        });
    }

    var accounts = read("council-accounts-data");
    var accountsCanvas = document.getElementById("council-accounts-chart");
    if (accounts && accountsCanvas) {
        new Chart(accountsCanvas, {
            type: "bar",
            data: {
                labels: accounts.years,
                datasets: accounts.services.map(function (s) {
                    return { label: s.name, data: s.years.map(function (y) { return y.value; }) };
                }),
            },
            options: options(true),
        });
    }
})();
