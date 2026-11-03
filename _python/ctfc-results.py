#!/usr/bin/env python3
"""Cheltenham Town's league history from football-data.co.uk: every season's
league table and Cheltenham's matches, and their record against each
opponent and under each referee. Writes:

  _data/ctfc-seasons/<season>.json     one per season: the table and Cheltenham's matches
  _data/ctfc-opponents/<slug>.json     one per opponent: record and every meeting
  _data/ctfc-referees.json             record under each referee
  _data/ctfc-summary.json              season-by-season record and the opponents table

Runs four times a day (refresh-4-times-daily.yml), before cheltenham-town-fc.py:
downloads the current season's file to
_data-sources/football/, rewrites that season and rebuilds the records from
every season file. To rebuild every season from the local copies made by
_python/local/football-data-download.py, run with --all.

Match statistics, half-time scores and referees start in 2000-01, so the
opponent and referee records start there too; 1999-2000 appears only in the
season-by-season record. Hand-written inputs:

  _data/ctfc-clubs.json            full club names for football-data's short ones
  _data/ctfc-referee-names.json    referee spellings to merge or keep apart
  _data/ctfc-corrections.json      points deductions and how a season's table was decided

  Source: https://football-data.co.uk/englandm.php (key: https://football-data.co.uk/notes.txt)
"""
import argparse
import csv
import io
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

import helper

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "_data"
LOCAL = ROOT / "_data-sources" / "football"
SEASONS_DIR = DATA / "ctfc-seasons"
OPPONENTS_DIR = DATA / "ctfc-opponents"

SOURCE = "Football-Data.co.uk"
SOURCE_URL = "https://football-data.co.uk/englandm.php"
FILE_URL = "https://football-data.co.uk/mmz4281/{code}/{division}.csv"

TEAM = "Cheltenham"
STATS_FROM = "2000-01"  # first season with half-time scores, referees and match statistics

# Division codes, named by each tier's current name so a file keeps its name across the 2004 rebrand.
DIVISIONS = {"E1": "championship", "E2": "league-one", "E3": "league-two", "EC": "national-league"}
OLD_NAMES = {"E1": "Division One", "E2": "Division Two", "E3": "Division Three"}
NEW_NAMES = {"E1": "Championship", "E2": "League One", "E3": "League Two", "EC": "National League"}
TIERS = {"E1": "second", "E2": "third", "E3": "fourth", "EC": "fifth"}
# Clubs in the divisions above each one, from the Premier League's 20 and 24 in each Football League
# division (the sizes since 1995-96, so every season here), for a club's rank in the 92.
CLUBS_ABOVE = {"E1": 20, "E2": 44, "E3": 68, "EC": 92}

# Match statistics as (our name, home column, away column), from football-data's notes.txt.
STATS = [
    ("shots", "HS", "AS"),
    ("shots_on_target", "HST", "AST"),
    ("woodwork", "HHW", "AHW"),
    ("corners", "HC", "AC"),
    ("fouls", "HF", "AF"),
    ("free_kicks_conceded", "HFKC", "AFKC"),
    ("offsides", "HO", "AO"),
    ("yellow_cards", "HY", "AY"),
    ("red_cards", "HR", "AR"),
    ("booking_points", "HBP", "ABP"),
]
# The stats the pages show, in order. Woodwork, offsides and booking points are
# still read into the match data above, but football-data only recorded them
# in 2000-01 and 2001-02, so they are left off every page.
STAT_LABELS = {
    "shots": "Shots", "shots_on_target": "Shots on target", "corners": "Corners",
    "fouls": "Fouls", "free_kicks_conceded": "Free kicks conceded",
    "yellow_cards": "Yellow cards", "red_cards": "Red cards",
}
# Short column headings for the stats, explained in a key under each table.
STAT_ABBR = {
    "shots": "Sh", "shots_on_target": "SoT", "corners": "Co", "fouls": "Fo",
    "free_kicks_conceded": "FKC", "yellow_cards": "YC", "red_cards": "RC",
}


# --- names, seasons and dates ---

def slugify(text):
    text = re.sub(r"['’]", "", text.lower())
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def season_label(code):
    """'0506' -> '2005-06'."""
    first = int(code[:2])
    start = (1900 if first > 50 else 2000) + first
    return f"{start}-{code[2:]}"


def season_display(season):
    """'2005-06' -> '2005–06', with the century in full when it changes: '1999-00' -> '1999–2000'."""
    start = int(season[:4])
    return f"{start}–{start + 1}" if (start + 1) % 100 == 0 else season.replace("-", "–")


def season_code(start_year):
    """2026 -> '2627'."""
    return f"{start_year % 100:02d}{(start_year + 1) % 100:02d}"


def local_name(code, division):
    """'0506', 'E3' -> 'season-2005-2006-league-two.csv'."""
    start = int(season_label(code)[:4])
    return f"season-{start}-{start + 1}-{DIVISIONS[division]}.csv"


def division_name(division, season):
    if division in OLD_NAMES and season < "2004-05":
        return OLD_NAMES[division]
    return NEW_NAMES[division]


def iso_date(text):
    day, month, year = text.strip().split("/")
    year = int(year) + (2000 if len(year) == 2 and int(year) < 50 else 1900 if len(year) == 2 else 0)
    return f"{year:04d}-{int(month):02d}-{int(day):02d}"


def club(short, division, clubs):
    """Full name and slug for a football-data short name; a club can have a different name in one division."""
    entry = clubs.get(short, {})
    name = entry.get(division, {}).get("name") or entry.get("name") or short
    return {"name": name, "slug": slugify(name)}


def referee_names(spellings, overrides):
    """Each spelling of a referee's name -> one display name. Spellings are grouped by first initial and
    surname ("Armstrong, P.", "P Armstrong", "Paul Armstrong"), named by the full first name when exactly one
    is known. When two full first names share a group (Alan and Andrew Butler) they stay apart and the
    initial-only spellings keep the initial. Overrides map a spelling straight to a name."""
    def parts(s):
        s = " ".join(s.split())
        if "," in s:
            last, first = (x.strip() for x in s.split(",", 1))
            s = f"{first} {last}"
        words = re.sub(r"\.", " ", s).split()
        return words

    groups = defaultdict(list)
    for s in spellings:
        words = parts(s)
        if words:
            groups[(words[0][0].upper(), words[-1])].append((s, words))
    names = {}
    for (initial, surname), members in groups.items():
        firsts = {w[0] for _, w in members if len(w[0]) > 1}
        only = next(iter(firsts)) if len(firsts) == 1 else None
        for s, words in members:
            if only:
                names[s] = f"{only} {surname}"
            elif len(words[0]) > 1:
                names[s] = f"{words[0]} {surname}"
            else:
                names[s] = f"{initial} {surname}"
    names.update(overrides)
    return names


# --- reading files ---

def read_rows(path):
    raw = Path(path).read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    return [r for r in csv.DictReader(io.StringIO(text)) if (r.get("HomeTeam") or "").strip() and (r.get("FTHG") or "").strip()]


def number(value):
    value = (value or "").replace(",", "").strip()
    if not value:
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def outcome(gf, ga):
    return "W" if gf > ga else "D" if gf == ga else "L"


# --- matches and tables ---

def match(r, division, clubs, referees):
    """One match from Cheltenham's side: goals for and against, half-time, statistics as [for, against]."""
    home = r["HomeTeam"].strip() == TEAM
    opp = club((r["AwayTeam"] if home else r["HomeTeam"]).strip(), division, clubs)
    fthg, ftag = number(r["FTHG"]), number(r["FTAG"])
    hthg, htag = number(r.get("HTHG")), number(r.get("HTAG"))
    gf, ga = (fthg, ftag) if home else (ftag, fthg)
    ht_gf, ht_ga = (hthg, htag) if home else (htag, hthg)
    has_ht = ht_gf is not None and ht_ga is not None
    stats = {}
    for name, hcol, acol in STATS:
        h, a = number(r.get(hcol)), number(r.get(acol))
        if h is not None and a is not None:
            stats[name] = [h, a] if home else [a, h]
    referee_raw = " ".join((r.get("Referee") or "").split()) or None
    referee = referees.get(referee_raw, referee_raw) if referee_raw else None
    attendance = number(r.get("Attendance"))
    m = {
        "date": iso_date(r["Date"]),
        "venue": "H" if home else "A",
        "opponent": opp["name"],
        "opponent_slug": opp["slug"],
        "gf": gf, "ga": ga, "result": outcome(gf, ga),
        "ht_gf": ht_gf if has_ht else None, "ht_ga": ht_ga if has_ht else None,
        "ht_result": outcome(ht_gf, ht_ga) if has_ht else None,
        "referee": referee, "referee_slug": slugify(referee) if referee else None, "referee_raw": referee_raw,
        "stats": stats,
    }
    if attendance:
        m["attendance"] = attendance
        m["attendance_display"] = f"{attendance:,}"
    return m


def ppg(points, played):
    value = round(points / played, 2) if played else 0.0
    return value, f"{value:.2f}"


def league_table(rows, division, clubs, correction):
    """Final (or current) table from every result, less any points deductions. Sorted by points, goal
    difference then goals scored, or by points per game when the season was decided that way."""
    teams = defaultdict(lambda: {"played": 0, "won": 0, "drawn": 0, "lost": 0, "gf": 0, "ga": 0})
    for r in rows:
        h, a = number(r["FTHG"]), number(r["FTAG"])
        for team, gf, ga in ((r["HomeTeam"].strip(), h, a), (r["AwayTeam"].strip(), a, h)):
            t = teams[team]
            t["played"] += 1
            t["gf"] += gf
            t["ga"] += ga
            t[{"W": "won", "D": "drawn", "L": "lost"}[outcome(gf, ga)]] += 1
    deducted = Counter()
    for d in correction.get("deductions", []):
        deducted[d["club"]] += d["points"]
    table = []
    for short, t in teams.items():
        c = club(short, division, clubs)
        points = 3 * t["won"] + t["drawn"] - deducted[short]
        value, display = ppg(points, t["played"])
        table.append({"club": c["name"], "slug": c["slug"], **t, "gd": t["gf"] - t["ga"],
                      "deducted": deducted[short], "points": points, "ppg": value, "ppg_display": display,
                      "is_cheltenham": short == TEAM})
    if correction.get("sort") == "ppg":
        table.sort(key=lambda t: (-t["points"] / max(t["played"], 1), -t["gd"], -t["gf"], t["club"]))
    else:
        table.sort(key=lambda t: (-t["points"], -t["gd"], -t["gf"], t["club"]))
    order = correction.get("order")
    if order:  # an official order that the tie-breaks above can't reproduce
        rank = {name: i for i, name in enumerate(order)}
        table.sort(key=lambda t: rank.get(t["club"], len(rank)))
    for i, t in enumerate(table, 1):
        t["position"] = i
    return table


# --- records ---

def record(games):
    """Played, won, drawn, lost, goals and points overall, at home and away; goals by half and results
    from each half-time position (where half-time is known); and match statistics for and against."""
    def tally(subset):
        won = sum(g["result"] == "W" for g in subset)
        drawn = sum(g["result"] == "D" for g in subset)
        gf, ga = sum(g["gf"] for g in subset), sum(g["ga"] for g in subset)
        points = 3 * won + drawn
        value, display = ppg(points, len(subset))
        n = len(subset)
        lost = n - won - drawn
        pct = {f"{k}_pct_display": f"{round(100 * v / n)}%" if n else "" for k, v in
               (("win", won), ("draw", drawn), ("loss", lost))}
        return {"played": n, "played_display": f"{n:,}", "won": won, "drawn": drawn, "lost": lost, **pct,
                "gf": gf, "ga": ga, "gd": gf - ga, "points": points, "ppg": value, "ppg_display": display}

    with_ht = [g for g in games if g["ht_result"] is not None]
    halves = {"games": len(with_ht),
              "first_gf": sum(g["ht_gf"] for g in with_ht), "first_ga": sum(g["ht_ga"] for g in with_ht),
              "second_gf": sum(g["gf"] - g["ht_gf"] for g in with_ht),
              "second_ga": sum(g["ga"] - g["ht_ga"] for g in with_ht)}
    states = {"W": "ahead", "D": "level", "L": "behind"}
    from_ht = {state: {"W": 0, "D": 0, "L": 0} for state in states.values()}
    for g in with_ht:
        from_ht[states[g["ht_result"]]][g["result"]] += 1
    by_ht = {state: tally([g for g in with_ht if g["ht_result"] == code]) for code, state in states.items()}
    stats = {}
    for name, _, _ in STATS:
        played = [g["stats"][name] for g in games if name in g["stats"]]
        if played:
            f, a = sum(p[0] for p in played), sum(p[1] for p in played)
            stats[name] = {"games": len(played), "for": f, "against": a,
                           "for_avg": f"{f / len(played):.1f}", "against_avg": f"{a / len(played):.1f}"}
    conditions = [{"group": "Half-time", "label": label, **by_ht[state]}
                  for state, label in (("ahead", "Ahead at HT"), ("level", "Level at HT"), ("behind", "Behind at HT"))]
    for name in CONDITION_STATS:
        with_stat = [g for g in games if name in g["stats"]]
        if not with_stat:
            continue
        label = STAT_LABELS[name].lower()
        for word, test in (("More", lambda s: s[0] > s[1]), ("Same", lambda s: s[0] == s[1]),
                           ("Fewer", lambda s: s[0] < s[1])):
            subset = [g for g in with_stat if test(g["stats"][name])]
            conditions.append({"group": STAT_LABELS[name], "label": f"{word} {label}", **tally(subset)})
    return {"all": tally(games), "home": tally([g for g in games if g["venue"] == "H"]),
            "away": tally([g for g in games if g["venue"] == "A"]),
            "halves": halves, "from_half_time": from_ht, "by_half_time": by_ht, "stats": stats,
            "conditions": conditions}


# Stats whose edge over the opponent (more, the same or fewer) splits the record.
CONDITION_STATS = ["shots", "shots_on_target", "corners", "fouls", "yellow_cards", "red_cards"]



def biggest(games, result):
    """The widest win or defeat, most recent first on a tie."""
    pool = [g for g in games if g["result"] == result]
    return max(pool, key=lambda g: (abs(g["gf"] - g["ga"]), g["gf"] + g["ga"], g["date"]), default=None)


# --- building the files ---

def load_json(path, default):
    return json.loads(Path(path).read_text()) if Path(path).exists() else default


def name_referees(seasons, overrides):
    """Give every match's referee one name, grouping spellings across all seasons at once."""
    names = referee_names({m["referee_raw"] for s in seasons for m in s["matches"] if m.get("referee_raw")}, overrides)
    for s in seasons:
        for m in s["matches"]:
            raw = m.get("referee_raw")
            m["referee"] = names.get(raw, raw) if raw else None
            m["referee_slug"] = slugify(m["referee"]) if m["referee"] else None
            m["referee_sort"] = surname_first(m["referee"]) if m["referee"] else None


def surname_first(name):
    """'Scott Mathieson' -> 'Mathieson, Scott', for referee lists sorted by surname."""
    first, _, surname = name.rpartition(" ")
    return f"{surname}, {first}" if first else surname


def build_season(path, code, division, clubs, corrections):
    rows = read_rows(path)
    season = season_label(code)
    correction = corrections.get(season, {})
    table = league_table(rows, division, clubs, correction)
    games = sorted((match(r, division, clubs, {}) for r in rows if TEAM in (r["HomeTeam"].strip(), r["AwayTeam"].strip())),
                   key=lambda m: m["date"])
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": SOURCE,
        "source_url": SOURCE_URL,
        "season": season,
        "season_display": season_display(season),
        "division": division_name(division, season),
        "division_code": division,
        "sorted_by": "points per game" if correction.get("sort") == "ppg" else "points",
        "note": correction.get("note"),
        "deductions": [{**d, "club": club(d["club"], division, clubs)["name"]} for d in correction.get("deductions", [])],
        "complete": all(t["played"] == 2 * (len(table) - 1) for t in table) or bool(correction.get("complete")),
        "table": table,
        "record": record(games),
        "matches": games,
    }


def rank_in_92(division_code, position):
    """Rank among the 92 Premier League and Football League clubs, 1 being the Premier League
    champions; a National League club ranks 93 or lower."""
    return CLUBS_ABOVE[division_code] + position


def build_records(seasons):
    """Opponent files, referee summary and the season-by-season summary from every season file."""
    games = [dict(m, season=s["season"], season_display=s["season_display"], division=s["division"])
             for s in seasons if s["season"] >= STATS_FROM for m in s["matches"]]
    games.sort(key=lambda g: g["date"], reverse=True)

    opponents = []
    for slug in sorted({g["opponent_slug"] for g in games}):
        theirs = [g for g in games if g["opponent_slug"] == slug]
        opponents.append({"club": theirs[0]["opponent"], "slug": slug, "since": STATS_FROM,
                          "first": theirs[-1]["date"], "last": theirs[0]["date"], "record": record(theirs),
                          "biggest_win": biggest(theirs, "W"), "biggest_defeat": biggest(theirs, "L"),
                          "meetings": theirs})

    referees = []
    for slug in sorted({g["referee_slug"] for g in games if g["referee_slug"]}):
        theirs = [g for g in games if g["referee_slug"] == slug]
        referees.append({"name": theirs[0]["referee"], "sort_name": theirs[0]["referee_sort"], "slug": slug,
                         "first": theirs[-1]["date"], "last": theirs[0]["date"], "record": record(theirs),
                         "matches": theirs})
    referees.sort(key=lambda r: r["sort_name"].lower())

    rows = []
    for s in sorted(seasons, key=lambda s: s["season"], reverse=True):
        mine = next(t for t in s["table"] if t["is_cheltenham"])
        rows.append({"season": s["season"], "season_display": s["season_display"], "division": s["division"],
                     "teams": len(s["table"]), "complete": s["complete"], "sorted_by": s["sorted_by"],
                     "has_table": s["season"] >= STATS_FROM, "tier": TIERS[s["division_code"]],
                     "rank_92": rank_in_92(s["division_code"], mine["position"]),
                     **{k: mine[k] for k in ("position", "played", "won", "drawn", "lost", "gf", "ga", "gd",
                                             "deducted", "points", "ppg", "ppg_display")},
                     "home": record([m for m in s["matches"] if m["venue"] == "H"])["all"],
                     "away": record([m for m in s["matches"] if m["venue"] == "A"])["all"]})
    summary_opponents = [{k: o[k] for k in ("club", "slug", "first", "last")} | {"record": o["record"]["all"]}
                         for o in opponents]
    summary_referees = [{k: r[k] for k in ("name", "sort_name", "slug", "first", "last")}
                        | {"record": r["record"]["all"],
                           "cards": {k: r["record"]["stats"].get(k) for k in ("yellow_cards", "red_cards")}}
                        for r in referees]
    since = record(games)
    stamp = {"generated_at": datetime.now(timezone.utc).isoformat(), "source": SOURCE, "source_url": SOURCE_URL}
    summary = {**stamp, "stats_from": STATS_FROM, "stats_from_display": STATS_FROM.replace("-", "–"),
               "stat_labels": STAT_LABELS, "stat_abbr": STAT_ABBR,
               "current": rows[0], "seasons": rows, "since_record": since["all"],
               "since_home": since["home"], "since_away": since["away"], "since_conditions": since["conditions"],
               "titles": [r for r in rows if r["position"] == 1 and r["complete"]],
               "league_seasons": sum(r["division"] != "National League" for r in rows),
               "opponents": summary_opponents, "matches": len(games)}
    referee_file = {**stamp, "stats_from": STATS_FROM, "stats_from_display": STATS_FROM.replace("-", "–"),
                    "referees": referees, "table": summary_referees}
    return opponents, referee_file, summary


def write_all(seasons):
    opponents, referees, summary = build_records(seasons)
    OPPONENTS_DIR.mkdir(parents=True, exist_ok=True)
    keep = set()
    for o in opponents:
        path = OPPONENTS_DIR / f"{o['slug']}.json"
        keep.add(path.name)
        helper.write_json(path, {"generated_at": summary["generated_at"], "source": SOURCE, "source_url": SOURCE_URL, **o})
    for stale in OPPONENTS_DIR.glob("*.json"):
        if stale.name not in keep:
            stale.unlink()
    helper.write_json(DATA / "ctfc-referees.json", referees)
    helper.write_json(DATA / "ctfc-summary.json", summary)
    print(f"Wrote {len(seasons)} seasons, {len(opponents)} opponents, {len(referees['referees'])} referees, "
          f"{summary['matches']} matches since {STATS_FROM}")


def find_team_file(code):
    """The local file for a season that has Cheltenham in it, and its division."""
    for division in DIVISIONS:
        path = LOCAL / local_name(code, division)
        if path.exists() and any(TEAM in (r["HomeTeam"].strip(), r["AwayTeam"].strip()) for r in read_rows(path)):
            return path, division
    return None, None


def download_current(code):
    """Fetch the current season's file for each division until one has Cheltenham in it."""
    LOCAL.mkdir(parents=True, exist_ok=True)
    for division in DIVISIONS:
        resp = helper.get(FILE_URL.format(code=code, division=division), timeout=60)
        if resp.status_code != 200:
            continue
        path = LOCAL / local_name(code, division)
        path.write_bytes(resp.content)
        if any(TEAM in (r["HomeTeam"].strip(), r["AwayTeam"].strip()) for r in read_rows(path)):
            return path, division
    return None, None


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--all", action="store_true", help="rebuild every season from _data-sources/football/")
    args = parser.parse_args()

    clubs = load_json(DATA / "ctfc-clubs.json", {}).get("clubs", {})
    overrides = load_json(DATA / "ctfc-referee-names.json", {}).get("overrides", {})
    corrections = load_json(DATA / "ctfc-corrections.json", {}).get("seasons", {})
    SEASONS_DIR.mkdir(parents=True, exist_ok=True)

    seasons = {p.stem: json.loads(p.read_text()) for p in sorted(SEASONS_DIR.glob("*.json"))}
    if args.all:
        for span in sorted({p.name[7:16] for p in LOCAL.glob("season-*.csv")}):  # '2005-2006'
            code = season_code(int(span[:4]))
            path, division = find_team_file(code)
            if path:
                s = build_season(path, code, division, clubs, corrections)
                seasons[s["season"]] = s
    else:
        today = date.today()
        code = season_code(today.year if today.month >= 7 else today.year - 1)
        path, division = download_current(code)
        if not path:
            sys.exit(f"No {code} season file with {TEAM} in it yet")
        s = build_season(path, code, division, clubs, corrections)
        seasons[s["season"]] = s

    ordered = [seasons[k] for k in sorted(seasons)]
    name_referees(ordered, overrides)
    for s in ordered:
        helper.write_json(SEASONS_DIR / f"{s['season']}.json", s)
    write_all(ordered)


if __name__ == "__main__":
    main()
