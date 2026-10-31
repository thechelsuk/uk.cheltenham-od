"""Offline tests for the public health fetcher (public-health.py): picking the
latest Cheltenham figure, matching England's figure on the same sex and age,
the life expectancy series and the ward table. Rows are built in memory, so
nothing calls the Fingertips API.

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import importlib.util
import pathlib

SPEC = importlib.util.spec_from_file_location(
    "public_health", pathlib.Path(__file__).resolve().parents[1] / "public-health.py"
)
assert SPEC is not None and SPEC.loader is not None
ph = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ph)


def row(code, value, indicator="93088", sex="Persons", age="18+ yrs", period="2024/25", sortable="20240000",
        compared="Similar", trend="", category="", period_range="1y", count="", parent="", name=None):
    return {
        "Indicator ID": indicator, "Area Code": code, "Area Name": name or code, "Parent Code": parent,
        "Sex": sex, "Age": age, "Category Type": category, "Time period": period,
        "Time period Sortable": sortable, "Time period range": period_range, "Value": value,
        "Compared to England value or percentiles": compared, "Recent Trend": trend, "Count": count,
    }


def test_keep_drops_other_areas_and_category_breakdowns():
    rows = [row("E07000078", "65.7"), row("E07000079", "60"), row("E92000001", "64.6"),
            row("E07000078", "70", category="Deprivation deciles")]
    kept = list(ph.keep(rows, {"E07000078", "E92000001"}))
    assert [r["Value"] for r in kept] == ["65.7", "64.6"]


def test_england_is_matched_on_the_same_sex_and_age():
    """England publishes every age band; the 18-24 figure must not be used
    as the all-adults comparison."""
    rows = [
        row("E92000001", "38.582", age="18-24 yrs"),
        row("E92000001", "64.642"),
        row("E07000078", "65.735"),
    ]
    entry = ph.latest_entry(rows, {"id": 93088, "label": "Overweight adults", "unit": "%"}, "Persons")
    assert entry["value"] == 65.7
    assert entry["england"] == 64.6
    assert entry["england_display"] == "64.6%"


def test_latest_period_wins_and_range_filter_applies():
    rows = [
        row("E07000078", "80.4", indicator="90366", sex="Male", age="All ages", period="2023 - 25",
            sortable="20230000", period_range="3y"),
        row("E07000078", "79.5", indicator="90366", sex="Male", age="All ages", period="2023", sortable="20230000"),
        row("E07000078", "81", indicator="90366", sex="Male", age="All ages", period="2025", sortable="20250000",
            compared="Better"),
        row("E92000001", "80", indicator="90366", sex="Male", age="All ages", period="2025", sortable="20250000",
            compared="Not compared"),
    ]
    config = {"id": 90366, "label": "Life expectancy at birth", "unit": "years", "range": "1y"}
    entry = ph.latest_entry(rows, config, "Male")
    assert entry["period"] == "2025"
    assert entry["value_display"] == "81.0 years"
    assert entry["compared"] == "Better"
    assert entry["compared_display"] == "Better than England"


def test_missing_cheltenham_value_gives_no_entry():
    rows = [row("E07000078", "", sex="Female"), row("E92000001", "5.5", sex="Female")]
    assert ph.latest_entry(rows, {"id": 93088, "label": "x", "unit": "%"}, "Female") is None


def test_display_formats_by_unit():
    assert ph.display(347.97, "per 100,000") == "348 per 100,000"
    assert ph.display(1234.6,"per 100,000") == "1,235 per 100,000"
    assert ph.display(9.52, "%") == "9.5%"
    assert ph.display(12.22, "years") == "12.2 years"


def test_period_display_uses_an_en_dash():
    assert ph.period_display("2022 - 24") == "2022–24"
    assert ph.period_display("2022/23 - 24/25") == "2022/23–24/25"
    assert ph.period_display("2025") == "2025"


def test_compared_display_for_unranked_indicators():
    assert ph.compared_display("Not compared") == "Not compared"
    assert ph.compared_display("Higher") == "Higher than England"
    assert ph.compared_display("") == "Not compared"


def test_life_expectancy_series_lines_up_by_year():
    rows = []
    for year, m, f in (("2024", "80.8", "84.0"), ("2025", "81", "84.2")):
        sortable = f"{year}0000"
        for code, shift in (("E07000078", 0), ("E92000001", -1)):
            rows.append(row(code, str(float(m) + shift), indicator="90366", sex="Male", age="All ages",
                            period=year, sortable=sortable))
            rows.append(row(code, str(float(f) + shift), indicator="90366", sex="Female", age="All ages",
                            period=year, sortable=sortable))
    rows.append(row("E07000078", "80.4", indicator="90366", sex="Male", age="All ages", period="2023 - 25",
                    sortable="20230000", period_range="3y"))
    series = ph.life_expectancy_series(rows, 90366)
    assert [p["year"] for p in series] == ["2024", "2025"]
    assert series[-1] == {"year": "2025", "male": 81.0, "female": 84.2, "england_male": 80.0, "england_female": 83.2}


def test_ward_table_uses_the_latest_period_and_ward_slugs():
    rows = [
        row("E05015717", "40.1", indicator="93108", age="10-11 yrs", period="2021/22 - 23/24", sortable="20210000",
            parent="E07000078", name="Springbank"),
        row("E05015717", "43.63", indicator="93108", age="10-11 yrs", period="2022/23 - 24/25", sortable="20220000",
            parent="E07000078", name="Springbank", count="120", compared="Worse"),
        row("E05015709", "16.66", indicator="93108", age="10-11 yrs", period="2022/23 - 24/25", sortable="20220000",
            parent="E07000078", name="College", count="15", compared="Better"),
        row("E05099999", "50", indicator="93108", age="10-11 yrs", period="2022/23 - 24/25", sortable="20220000",
            parent="E07000079", name="Elsewhere"),
        row("E07000078", "30.66", indicator="93108", age="10-11 yrs", period="2022/23 - 24/25", sortable="20220000"),
        row("E92000001", "36.19", indicator="93108", age="10-11 yrs", period="2022/23 - 24/25", sortable="20220000"),
    ]
    slugs = {"E05015717": "springbank", "E05015709": "college"}
    table = ph.ward_table(rows, 93108, slugs)
    assert table["period"] == "2022/23 - 24/25"
    assert table["cheltenham_display"] == "30.7%"
    assert table["england_display"] == "36.2%"
    assert [w["name"] for w in table["rows"]] == ["College", "Springbank"]
    springbank = table["rows"][1]
    assert springbank == {"code": "E05015717", "name": "Springbank", "slug": "springbank", "value": 43.6,
                          "value_display": "43.6%", "count": 120, "compared": "Worse",
                          "compared_display": "Worse than England"}


def test_build_counts_comparisons_and_skips_missing_indicators():
    rows = [
        row("E07000078", "81", indicator="90366", sex="Male", age="All ages", compared="Better"),
        row("E92000001", "80", indicator="90366", sex="Male", age="All ages"),
        row("E07000078", "84.2", indicator="90366", sex="Female", age="All ages"),
        row("E07000078", "12", indicator="41001", compared="Worse"),
    ]
    curated = {
        "groups": [
            {"name": "Life Expectancy", "indicators": [
                {"id": 90366, "label": "Life expectancy at birth", "unit": "years", "sexes": ["Male", "Female"]}]},
            {"name": "Deaths", "indicators": [{"id": 41001, "label": "Suicide rate", "unit": "per 100,000"}]},
            {"name": "Empty", "indicators": [{"id": 1, "label": "Nothing", "unit": "%"}]},
        ],
        "life_expectancy_chart": 90366,
        "ward_indicator": {"id": 93108, "label": "Year 6"},
    }
    output = ph.build(curated, rows, [], {})
    assert [g["name"] for g in output["groups"]] == ["Life Expectancy", "Deaths"]
    assert output["groups"][0]["indicators"][0]["label_display"] == "Life expectancy at birth (men)"
    assert (output["indicator_count"], output["better_count"], output["worse_count"]) == (3, 1, 1)
    assert output["wards"] is None
