(function () {
    var dataEl = document.getElementById("energy-use-data");
    if (!dataEl || typeof Chart === "undefined") return;

    var years = [];
    try {
        years = JSON.parse(dataEl.textContent) || [];
    } catch (e) {
        return;
    }
    if (!years.length) return;

    var places = ["Cheltenham", "South West", "England"];

    // One line per place, so Cheltenham keeps its colour from the site palette.
    function draw(id, key) {
        var el = document.getElementById(id);
        if (!el) return;
        new Chart(el, {
            type: "line",
            data: {
                labels: years.map(function (y) { return y.year; }),
                datasets: places.map(function (place) {
                    return {
                        label: place,
                        data: years.map(function (y) { return y[key][place]; }),
                        fill: false,
                    };
                }),
            },
            options: {
                responsive: true,
                scales: { y: { beginAtZero: false, title: { display: true, text: "kWh per home" } } },
            },
        });
    }

    draw("energy-use-electricity-chart", "electricity_mean_kwh");
    draw("energy-use-gas-chart", "gas_mean_kwh");
})();
