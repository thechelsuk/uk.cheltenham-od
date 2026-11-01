"""Offline tests for the Cheltenham Town league history job (ctfc-results.py):
reading football-data.co.uk season files, league tables with deductions and
points per game, matches from Cheltenham's side, and the opponent and
referee records built from them.

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import importlib.util
import pathlib

SPEC = importlib.util.spec_from_file_location(
    "ctfc_results", pathlib.Path(__file__).resolve().parents[1] / "ctfc-results.py"
)
assert SPEC is not None and SPEC.loader is not None
ctfc = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ctfc)

CLUBS = {
    "Cheltenham": {"name": "Cheltenham Town"},
    "Forest Green": {"name": "Forest Green Rovers"},
    "Chester": {"name": "Chester City", "EC": {"name": "Chester"}},
    "Bury": {"name": "Bury"},
}


def row(home, away, fthg, ftag, hthg="", htag="", **extra):
    base = {"Div": "E3", "Date": "07/08/04", "HomeTeam": home, "AwayTeam": away,
            "FTHG": str(fthg), "FTAG": str(ftag), "HTHG": str(hthg), "HTAG": str(htag)}
    base.update({k: str(v) for k, v in extra.items()})
    return base


def test_season_labels_and_file_names():
    assert ctfc.season_label("0506") == "2005-06"
    assert ctfc.season_label("9900") == "1999-00"
    assert ctfc.season_code(2026) == "2627"
    assert ctfc.local_name("0506", "E3") == "season-2005-2006-league-two.csv"


def test_division_names_follow_the_2004_rebrand():
    assert ctfc.division_name("E3", "2003-04") == "Division Three"
    assert ctfc.division_name("E3", "2004-05") == "League Two"
    assert ctfc.division_name("E2", "2002-03") == "Division Two"
    assert ctfc.division_name("EC", "2015-16") == "National League"


def test_dates_in_two_and_four_digit_years():
    assert ctfc.iso_date("07/08/04") == "2004-08-07"
    assert ctfc.iso_date("12/08/2023") == "2023-08-12"


def test_club_names_can_differ_by_division():
    assert ctfc.club("Chester", "E3", CLUBS) == {"name": "Chester City", "slug": "chester-city"}
    assert ctfc.club("Chester", "EC", CLUBS) == {"name": "Chester", "slug": "chester"}
    assert ctfc.club("Unknown FC", "E3", CLUBS) == {"name": "Unknown FC", "slug": "unknown-fc"}


def test_referee_names_group_spellings():
    names = ["P Armstrong", "Armstrong, P.", "Paul Armstrong", "A Butler", "Alan Butler", "Andrew Butler",
             "Butler, A. N.", "P  Wright"]
    canon = ctfc.referee_names(names, overrides={})
    assert canon["Armstrong, P."] == canon["P Armstrong"] == canon["Paul Armstrong"] == "Paul Armstrong"
    # Two different full first names: keep them apart, and keep the initial-only ones as "A Butler".
    assert canon["Alan Butler"] == "Alan Butler" and canon["Andrew Butler"] == "Andrew Butler"
    assert canon["A Butler"] == canon["Butler, A. N."] == "A Butler"
    assert canon["P  Wright"] == "P Wright"
    assert ctfc.referee_names(["A Butler"], overrides={"A Butler": "Andrew Butler"})["A Butler"] == "Andrew Butler"


def test_referee_surname_first():
    assert ctfc.surname_first("Scott Mathieson") == "Mathieson, Scott"
    assert ctfc.surname_first("Andy D'Urso") == "D'Urso, Andy"
    assert ctfc.surname_first("A Butler") == "Butler, A"
    assert ctfc.surname_first("Mathieson") == "Mathieson"


def test_referees_are_named_across_seasons():
    seasons = [{"matches": [{"referee_raw": "P Armstrong"}]}, {"matches": [{"referee_raw": "Paul Armstrong"}, {"referee_raw": None}]}]
    ctfc.name_referees(seasons, {})
    assert seasons[0]["matches"][0]["referee"] == seasons[1]["matches"][0]["referee"] == "Paul Armstrong"
    assert seasons[0]["matches"][0]["referee_slug"] == "paul-armstrong"
    assert seasons[0]["matches"][0]["referee_sort"] == "Armstrong, Paul"
    assert seasons[1]["matches"][1]["referee"] is None


def test_match_from_cheltenhams_side_with_stats_for_and_against():
    m = ctfc.match(row("Forest Green", "Cheltenham", 1, 3, 1, 0, HS=12, AS=9, HY=2, AY=1, Referee="P Armstrong",
                       Attendance="4,512"),
                   "E3", CLUBS, {"P Armstrong": "Paul Armstrong"})
    assert m["venue"] == "A" and m["opponent"] == "Forest Green Rovers" and m["opponent_slug"] == "forest-green-rovers"
    assert (m["gf"], m["ga"], m["result"]) == (3, 1, "W")
    assert (m["ht_gf"], m["ht_ga"], m["ht_result"]) == (0, 1, "L")
    assert m["stats"] == {"shots": [9, 12], "yellow_cards": [1, 2]}
    assert m["referee"] == "Paul Armstrong" and m["referee_slug"] == "paul-armstrong"
    assert m["attendance"] == 4512 and m["attendance_display"] == "4,512"


def test_match_without_half_time_or_stats():
    m = ctfc.match(row("Cheltenham", "Bury", 0, 0), "E3", CLUBS, {})
    assert m["ht_gf"] is None and m["ht_result"] is None and m["stats"] == {} and m["referee"] is None


def test_table_sorts_by_points_then_goal_difference_with_deductions():
    rows = [row("Cheltenham", "Bury", 2, 0), row("Bury", "Forest Green", 1, 1), row("Forest Green", "Cheltenham", 3, 0)]
    table = ctfc.league_table(rows, "E3", CLUBS, {"deductions": [{"club": "Forest Green", "points": 3}]})
    assert [t["club"] for t in table] == ["Cheltenham Town", "Forest Green Rovers", "Bury"]
    fg = table[1]
    assert (fg["played"], fg["won"], fg["drawn"], fg["lost"], fg["gf"], fg["ga"]) == (2, 1, 1, 0, 4, 1)
    assert (fg["deducted"], fg["points"], fg["ppg_display"]) == (3, 1, "0.50")
    assert table[0]["position"] == 1 and table[0]["is_cheltenham"] is True


def test_table_can_sort_by_points_per_game():
    rows = [row("Cheltenham", "Bury", 1, 0), row("Forest Green", "Bury", 1, 0), row("Forest Green", "Cheltenham", 0, 0)]
    # Forest Green 4 pts from 2, Cheltenham 4 pts from 2, Bury 0 from 2: add a game so PPG differs.
    rows.append(row("Bury", "Cheltenham", 0, 1))
    table = ctfc.league_table(rows, "E3", CLUBS, {"sort": "ppg"})
    assert [t["club"] for t in table][:2] == ["Cheltenham Town", "Forest Green Rovers"]
    assert table[0]["ppg_display"] == "2.33"


def test_record_counts_results_halves_and_half_time_states():
    games = [
        {"venue": "H", "gf": 2, "ga": 1, "ht_gf": 0, "ht_ga": 1, "result": "W", "ht_result": "L",
         "stats": {"yellow_cards": [1, 3], "red_cards": [0, 1]}},
        {"venue": "A", "gf": 0, "ga": 0, "ht_gf": 0, "ht_ga": 0, "result": "D", "ht_result": "D", "stats": {}},
        {"venue": "A", "gf": 1, "ga": 2, "ht_gf": None, "ht_ga": None, "result": "L", "ht_result": None, "stats": {}},
    ]
    rec = ctfc.record(games)
    assert rec["all"] == {"played": 3, "played_display": "3", "won": 1, "drawn": 1, "lost": 1,
                          "win_pct_display": "33%", "draw_pct_display": "33%", "loss_pct_display": "33%", "gf": 3, "ga": 3, "gd": 0, "points": 4,
                          "ppg": 1.33, "ppg_display": "1.33"}
    assert rec["home"]["played"] == 1 and rec["away"]["played"] == 2
    assert rec["halves"] == {"games": 2, "first_gf": 0, "first_ga": 1, "second_gf": 2, "second_ga": 0}
    assert rec["from_half_time"]["behind"] == {"W": 1, "D": 0, "L": 0}
    assert rec["from_half_time"]["level"] == {"W": 0, "D": 1, "L": 0}
    assert rec["stats"]["yellow_cards"] == {"games": 1, "for": 1, "against": 3, "for_avg": "1.0", "against_avg": "3.0"}


def test_record_by_half_time_has_full_rows():
    games = [
        {"venue": "H", "gf": 2, "ga": 1, "ht_gf": 1, "ht_ga": 0, "result": "W", "ht_result": "W", "stats": {}},
        {"venue": "A", "gf": 1, "ga": 1, "ht_gf": 1, "ht_ga": 0, "result": "D", "ht_result": "W", "stats": {}},
    ]
    ahead = ctfc.record(games)["by_half_time"]["ahead"]
    assert (ahead["played"], ahead["won"], ahead["drawn"], ahead["points"], ahead["ppg_display"]) == (2, 1, 1, 4, "2.00")
    assert ctfc.record(games)["by_half_time"]["behind"]["played"] == 0


def test_conditions_split_the_record_by_half_time_and_stat_edges():
    games = [
        {"venue": "H", "gf": 2, "ga": 0, "ht_gf": 1, "ht_ga": 0, "result": "W", "ht_result": "W",
         "stats": {"shots": [15, 8], "yellow_cards": [1, 3]}},
        {"venue": "A", "gf": 0, "ga": 1, "ht_gf": 0, "ht_ga": 0, "result": "L", "ht_result": "D",
         "stats": {"shots": [6, 12], "yellow_cards": [2, 2]}},
        {"venue": "A", "gf": 1, "ga": 1, "ht_gf": None, "ht_ga": None, "result": "D", "ht_result": None,
         "stats": {"shots": [9, 9]}},
    ]
    rows = {r["label"]: r for r in ctfc.record(games)["conditions"]}
    assert rows["Ahead at HT"]["played"] == 1 and rows["Ahead at HT"]["win_pct_display"] == "100%"
    assert rows["Level at HT"]["loss_pct_display"] == "100%"
    assert rows["Behind at HT"]["played"] == 0
    assert rows["More shots"]["won"] == 1 and rows["Fewer shots"]["lost"] == 1 and rows["Same shots"]["drawn"] == 1
    assert rows["Fewer yellow cards"]["won"] == 1 and rows["Same yellow cards"]["lost"] == 1
    assert rows["More shots"]["group"] == "Shots"
    assert "More red cards" not in rows  # no red card data in these games


def test_season_display_writes_the_century_in_full():
    assert ctfc.season_display("1999-00") == "1999–2000"
    assert ctfc.season_display("2005-06") == "2005–06"


def test_slugify():
    assert ctfc.slugify("Brighton & Hove Albion") == "brighton-hove-albion"
    assert ctfc.slugify("Andy D'Urso") == "andy-durso"
