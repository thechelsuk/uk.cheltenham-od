"""Offline tests for the school absence fetcher (school-absence.py): picking
the latest Department for Education data files from Explore Education
Statistics, building the Gloucestershire, South West and England series, and
the figures for each Cheltenham school. Rows are built in memory, so nothing
calls the DfE.

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import importlib.util
import pathlib

SPEC = importlib.util.spec_from_file_location(
    "school_absence", pathlib.Path(__file__).resolve().parents[1] / "school-absence.py"
)
assert SPEC is not None and SPEC.loader is not None
sa = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sa)


def entry(filename, published, release="Academic year 2024/25", slug="2024-25", superseded=False, id_="x"):
    return {
        "id": id_, "filename": filename, "published": published, "isSuperseded": superseded,
        "release": {"title": release, "slug": slug, "id": "r"},
    }


def geo_row(level, period, overall, pa, sa_, phase="Total", la="", region="", breakdown=None, enrolments="1000"):
    row = {
        "time_period": period, "geographic_level": level, "country_name": "England",
        "region_name": region, "la_name": la, "new_la_code": "E10000013" if la == "Gloucestershire" else "",
        "region_code": "E12000009" if region == "South West" else "",
        "education_phase": phase, "enrolments": enrolments, "num_schools": "10",
        "sess_overall_percent": overall, "enrolments_pa_10_exact_percent": pa,
        "enrolments_pa_50_exact_percent": sa_,
        "enrolments_pa_10_exact": "180", "enrolments_pa_50_exact": "24",
    }
    if breakdown is not None:
        row["year_breakdown"] = breakdown
    return row


def school_row(urn, period, overall, pa, sa_, phase="State-funded primary", name="A School", enrolments="200"):
    return {
        "time_period": period, "school_urn": urn, "school_name": name, "education_phase": phase,
        "enrolments": enrolments, "sess_overall_percent": overall,
        "enrolments_pa_10_exact_percent": pa, "enrolments_pa_50_exact_percent": sa_,
    }


# --- Choosing the files ------------------------------------------------------

def test_pick_files_takes_the_latest_of_each_kind():
    entries = [
        entry("1_absence_3term_nat_reg_la.csv", "2025-03-20T09:30:00", id_="old-fy-geo"),
        entry("1_Absence_3term_nat_reg_la.csv", "2026-03-26T09:30:00", id_="fy-geo"),
        entry("1a_Absence_3term_school.csv", "2026-03-26T09:30:00", id_="fy-school"),
        entry("Absence_2term_nat_reg_la.csv", "2026-10-15T08:30:00", "Autumn and spring term 2025/26", id_="tt-geo"),
        entry("Absence_2term_school.csv", "2026-10-15T08:30:00", "Autumn and spring term 2025/26", id_="tt-school"),
        entry("Absence_1term_nat_reg_la.csv", "2026-08-06T09:30:00", "Autumn term 2025/26", id_="autumn"),
        entry("Absence_2term_nat_reg_la_termly.csv", "2026-10-15T08:30:00", id_="termly"),
        entry("Absence_2term_4_year_olds_school.csv", "2026-10-15T08:30:00", id_="four"),
    ]
    picked = sa.pick_files(entries)
    assert {k: v["id"] for k, v in picked.items()} == {
        "full_year_geo": "fy-geo", "full_year_school": "fy-school",
        "two_term_geo": "tt-geo", "two_term_school": "tt-school",
    }


def test_pick_files_skips_superseded_files():
    entries = [
        entry("1_Absence_3term_nat_reg_la.csv", "2026-03-26T09:30:00", id_="new", superseded=True),
        entry("1_absence_3term_nat_reg_la.csv", "2025-03-20T09:30:00", id_="old"),
    ]
    assert sa.pick_files(entries)["full_year_geo"]["id"] == "old"


# --- Values and labels -------------------------------------------------------

def test_year_label():
    assert sa.year_label("202425") == "2024/25"
    assert sa.year_label("200910") == "2009/10"


def test_rate_reads_numbers_and_drops_suppressed_values():
    assert sa.rate("6.69829") == 6.7
    assert sa.rate("17.18098") == 17.18
    for value in ("c", "z", "x", "low", "", None):
        assert sa.rate(value) is None


def test_display():
    assert sa.display(6.69829) == "6.7%"
    assert sa.display(None) == "–"
    assert sa.display("c") == "–"


def test_display_rounds_the_unrounded_figure():
    """13.2468 is 13.2%, not 13.3% (which rounding 13.25 again would give)."""
    row = geo_row("National", "202425", "6.6", "13.2468", "1.0")
    series = sa.area_series([row])
    assert series[0]["england"]["persistent"] == 13.25
    assert series[0]["england_display"]["persistent"] == "13.2%"


# --- Area series -------------------------------------------------------------

def test_area_series_keeps_gloucestershire_south_west_and_england():
    rows = [
        geo_row("National", "202425", "6.78223", "18.14307", "2.38708", enrolments="7388150"),
        geo_row("Regional", "202425", "7.07312", "18.32122", "2.81692", region="South West"),
        geo_row("Regional", "202425", "5.9", "15", "2", region="London"),
        geo_row("Local authority", "202425", "6.69829", "17.18098", "2.35388", la="Gloucestershire",
                region="South West"),
        geo_row("Local authority", "202425", "7.5", "20", "3", la="South Gloucestershire", region="South West"),
        geo_row("Local authority", "202425", "4.1", "9", "1", la="Gloucestershire", phase="State-funded primary"),
    ]
    series = sa.area_series(rows)
    assert len(series) == 1
    year = series[0]
    assert year["year"] == "2024/25"
    assert year["gloucestershire"] == {"overall": 6.7, "persistent": 17.18, "severe": 2.35}
    assert year["south_west"]["severe"] == 2.82
    assert year["england"]["overall"] == 6.78
    assert year["gloucestershire_display"]["persistent"] == "17.2%"


def test_area_series_counts_pupils():
    rows = [geo_row("Local authority", "202425", "6.7", "17.18", "2.35", la="Gloucestershire",
                    enrolments="81695")]
    counts = sa.area_series(rows)[0]["gloucestershire_pupils"]
    assert counts == {"enrolments": 81695, "persistent": 180, "severe": 24,
                      "enrolments_display": "81,695", "persistent_display": "180", "severe_display": "24"}


def test_area_series_uses_six_half_terms_for_full_years():
    """Before 2012/13 the full year was five half terms; mixing the two would
    break the series, so only six-half-term years are kept."""
    rows = [
        geo_row("National", "201112", "5.1", "13.5", "0.6", breakdown="Five half terms"),
        geo_row("National", "201213", "5.26", "13.6", "0.58", breakdown="Six half terms"),
        geo_row("National", "202425", "6.78", "18.14", "2.39", breakdown="Six half terms"),
    ]
    assert [y["year"] for y in sa.area_series(rows)] == ["2012/13", "2024/25"]


def test_area_series_is_in_year_order_and_tolerates_a_missing_area():
    rows = [
        geo_row("National", "202425", "6.6", "17.6", "2.3"),
        geo_row("National", "202021", "4.0", "10.4", "1.1"),
    ]
    series = sa.area_series(rows)
    assert [y["year"] for y in series] == ["2020/21", "2024/25"]
    assert series[0]["gloucestershire"] is None
    assert series[0]["gloucestershire_display"] is None


def test_by_phase_gives_the_latest_year_for_each_phase():
    rows = [
        geo_row("National", "202425", "6.78", "18.1", "2.4"),
        geo_row("National", "202425", "5.5", "14.0", "1.0", phase="State-funded primary"),
        geo_row("National", "202425", "8.2", "23.0", "4.0", phase="State-funded secondary"),
        geo_row("National", "202324", "9.0", "26.0", "3.5", phase="State-funded secondary"),
        geo_row("Local authority", "202425", "8.0", "22.0", "4.1", la="Gloucestershire",
                phase="State-funded secondary"),
        geo_row("National", "202425", "6.9", "18", "2.5", phase="State-funded primary and secondary"),
    ]
    phases = sa.by_phase(rows)
    assert [p["phase"] for p in phases] == ["Primary", "Secondary"]
    secondary = phases[1]
    assert secondary["year"] == "2024/25"
    assert secondary["england"]["overall"] == 8.2
    assert secondary["gloucestershire"]["severe"] == 4.1
    assert secondary["south_west"] is None


# --- Schools -----------------------------------------------------------------

def test_school_figures_take_the_latest_year_for_our_schools_only():
    rows = [
        school_row("115000", "202324", "8.0", "22.0", "1.5", name="Old Name"),
        school_row("115000", "202425", "7.81787", "25.09363", "1.49813", name="Gardners Lane Primary School",
                   enrolments="1267"),
        school_row("999999", "202425", "5.0", "10.0", "1.0"),
        school_row("136016", "202425", "c", "c", "c", phase="State-funded secondary"),
    ]
    period, schools = sa.school_figures(rows, {"115000", "136016"})
    assert period == "2024/25"
    assert set(schools) == {"115000", "136016"}
    gardners = schools["115000"]
    assert gardners["enrolments"] == 1267
    assert gardners["enrolments_display"] == "1,267"
    assert gardners["overall"] == 7.82
    assert gardners["persistent"] == 25.09
    assert gardners["severe"] == 1.5
    assert gardners["overall_display"] == "7.8%"
    assert schools["136016"]["overall"] is None
    assert schools["136016"]["overall_display"] == "–"


def test_school_figures_ignore_a_school_missing_from_the_latest_year():
    rows = [
        school_row("115000", "202425", "7.8", "25", "1.5"),
        school_row("120000", "202324", "6.0", "15", "1.0"),
    ]
    period, schools = sa.school_figures(rows, {"115000", "120000"})
    assert period == "2024/25"
    assert set(schools) == {"115000"}


def test_school_figures_use_the_predecessor_urn_after_an_academy_conversion():
    """A school that became an academy gets a new URN; the DfE's figures for
    the year before can still be under the old one."""
    rows = [
        school_row("115648", "202425", "4.5", "9.0", "0.5", name="Sherborne Church of England Primary School"),
        school_row("200000", "202425", "6.0", "15.0", "1.0"),
        school_row("200001", "202425", "7.0", "16.0", "2.0"),
    ]
    aliases = {"115648": "151418", "200001": "200000"}
    period, schools = sa.school_figures(rows, {"151418", "200000"}, aliases)
    assert set(schools) == {"151418", "200000"}
    assert schools["151418"]["overall"] == 4.5
    # The school's own URN wins over a predecessor's in the same year.
    assert schools["200000"]["overall"] == 6.0


def test_predecessor_aliases_from_ofsted_data():
    ofsted = {"schools": {
        "151418": {"predecessors": [{"urn": "115648"}]},
        "136016": {"predecessors": []},
    }}
    assert sa.predecessor_aliases(ofsted) == {"115648": "151418"}


def test_urn_from_gias_link():
    url = "https://get-information-schools.service.gov.uk/Establishments/Establishment/Details/136016"
    assert sa.urn_from_url(url) == "136016"
    assert sa.urn_from_url(url + "/") == "136016"


def test_school_list_combines_both_releases_sorted_by_name():
    our_schools = [
        {"name": "Zeta School", "phase": "Primary", "urn_url": "https://x/Details/2"},
        {"name": "Alpha School", "phase": "Secondary", "urn_url": "https://x/Details/1"},
        {"name": "Cheltenham College", "phase": "Not applicable", "urn_url": "https://x/Details/3"},
    ]
    full_year = {"1": {"overall": 5.0, "enrolments": 900}, "2": {"overall": 4.0, "enrolments": 100}}
    two_term = {"1": {"overall": 4.8, "enrolments": 910}}
    listed = sa.school_list(our_schools, full_year, two_term)
    assert [s["name"] for s in listed] == ["Alpha School", "Zeta School"]
    assert listed[0]["urn"] == "1"
    assert listed[0]["full_year"]["overall"] == 5.0
    assert listed[0]["two_term"]["overall"] == 4.8
    assert listed[1]["two_term"] is None
