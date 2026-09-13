(function () {
    const widget = document.querySelector(".land-registry-widget");
    if (!widget) return;

    const dataElement = document.getElementById("house-price-data");
    const transactions = dataElement
        ? JSON.parse(dataElement.textContent || "[]")
        : [];
    renderChart(transactions);
    renderVolumeChart(transactions);
    renderTypeChart(transactions);
    renderHistogram(transactions);

    function formatPrice(amount) {
        return "£" + amount.toLocaleString("en-GB");
    }

    function renderChart(transactions) {
        const byMonth = {};
        transactions.forEach((t) => {
            if (!t.amount || !t.date) return;
            const month = t.date.slice(0, 7);
            if (!byMonth[month]) byMonth[month] = [];
            byMonth[month].push(t.amount);
        });

        const months = Object.keys(byMonth).sort();
        const medians = months.map((m) => {
            const vals = byMonth[m].slice().sort((a, b) => a - b);
            const mid = Math.floor(vals.length / 2);
            return vals.length % 2 !== 0
                ? vals[mid]
                : (vals[mid - 1] + vals[mid]) / 2;
        });

        new Chart(document.getElementById("land-registry-chart"), {
            type: "line",
            data: {
                labels: months,
                datasets: [
                    {
                        label: "Median sale price",
                        data: medians,
                        borderWidth: 2,
                        tension: 0.2,
                    },
                ],
            },
            options: {
                responsive: true,
                plugins: { legend: { display: false } },
                scales: { y: { ticks: { callback: (v) => formatPrice(v) } } },
            },
        });
    }

    function renderVolumeChart(transactions) {
        const byMonth = {};
        transactions.forEach((t) => {
            if (!t.amount || !t.date) return;
            const month = t.date.slice(0, 7);
            byMonth[month] = (byMonth[month] || 0) + 1;
        });

        const months = Object.keys(byMonth).sort();
        const counts = months.map((m) => byMonth[m]);

        new Chart(document.getElementById("land-registry-volume-chart"), {
            type: "bar",
            data: {
                labels: months,
                datasets: [
                    {
                        label: "Sales",
                        data: counts,
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

    function renderTypeChart(transactions) {
        const typeLabels = {
            D: "Detached",
            S: "Semi-detached",
            T: "Terraced",
            F: "Flat/Maisonette",
            O: "Other",
        };
        const byType = {};
        transactions.forEach((t) => {
            if (!t.amount) return;
            const key = t.property_type || "O";
            if (!byType[key]) byType[key] = [];
            byType[key].push(t.amount);
        });

        const types = Object.keys(byType);
        const labels = types.map((t) => typeLabels[t] || t);
        const medians = types.map((t) => {
            const vals = byType[t].slice().sort((a, b) => a - b);
            const mid = Math.floor(vals.length / 2);
            return vals.length % 2 !== 0
                ? vals[mid]
                : (vals[mid - 1] + vals[mid]) / 2;
        });

        new Chart(document.getElementById("land-registry-type-chart"), {
            type: "bar",
            data: {
                labels: labels,
                datasets: [
                    {
                        label: "Median price",
                        data: medians,
                    },
                ],
            },
            options: {
                responsive: true,
                plugins: { legend: { display: false } },
                scales: { y: { ticks: { callback: (v) => formatPrice(v) } } },
            },
        });
    }

    function renderHistogram(transactions) {
        const prices = transactions
            .map((t) => t.amount)
            .filter(Boolean)
            .sort((a, b) => a - b);
        if (prices.length === 0) return;

        // Use 5th-95th percentile to size buckets, so a handful of outliers
        // (very cheap leasehold/partial sales, very expensive properties)
        // don't stretch the range and collapse everything into one bucket.
        const p05 = prices[Math.floor(prices.length * 0.05)];
        const p95 = prices[Math.floor(prices.length * 0.95)];

        const bucketCount = 10;
        const rawBucketSize = (p95 - p05) / bucketCount;
        const bucketSize = Math.ceil(rawBucketSize / 5000) * 5000 || 5000;

        const buckets = {};
        let overflowCount = 0;

        prices.forEach((p) => {
            if (p > p95) {
                overflowCount++;
                return;
            }
            const bucketStart =
                p05 + Math.floor((p - p05) / bucketSize) * bucketSize;
            buckets[bucketStart] = (buckets[bucketStart] || 0) + 1;
        });

        const bucketKeys = Object.keys(buckets)
            .map(Number)
            .sort((a, b) => a - b);
        const labels = bucketKeys.map((k) => formatPrice(k));
        const counts = bucketKeys.map((k) => buckets[k]);

        if (overflowCount > 0) {
            labels.push(`${formatPrice(p95)}+`);
            counts.push(overflowCount);
        }

        new Chart(document.getElementById("land-registry-histogram"), {
            type: "bar",
            data: {
                labels: labels,
                datasets: [
                    {
                        label: "Sales",
                        data: counts,
                    },
                ],
            },
            options: {
                responsive: true,
                plugins: {
                    legend: { display: false },
                    title: { display: true, text: "Price distribution" },
                },
                scales: {
                    y: { beginAtZero: true, ticks: { precision: 0 } },
                    x: { ticks: { maxRotation: 45, minRotation: 45 } },
                },
            },
        });
    }
})();
