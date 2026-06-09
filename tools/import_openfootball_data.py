#!/usr/bin/env python3
"""Import public OpenFootball match data into the box-to-boxd SQLite database."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import re
import ssl
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import app  # noqa: E402


USER_AGENT = "box-to-boxd data importer/1.0"
FETCH_TIMEOUT = 20
RAW_GITHUB = "https://raw.githubusercontent.com/openfootball/{repo}/master/{path}"
FOOTBALL_DATA = "https://www.football-data.co.uk/mmz4281/{slug}/T1.csv"
TODAY = dt.date.today()
SSL_CONTEXT = ssl._create_unverified_context()

MONTHS = {
    "Jan": 1,
    "Feb": 2,
    "Mar": 3,
    "Apr": 4,
    "May": 5,
    "Jun": 6,
    "Jul": 7,
    "Aug": 8,
    "Sep": 9,
    "Oct": 10,
    "Nov": 11,
    "Dec": 12,
}


@dataclass(frozen=True)
class SourcePlan:
    league_code: str
    season: str
    source_name: str
    source_url: str
    parser: str


@dataclass(frozen=True)
class ParsedMatch:
    home_team: str
    away_team: str
    match_date: str
    home_score: int | None = None
    away_score: int | None = None
    round_name: str = ""
    stage: str = ""
    venue: str = ""


TEXT_SOURCES = {
    "premier-league": ("england", "{slug}/1-premierleague.txt", 2000, app.SEASON_END_YEAR),
    "bundesliga": ("deutschland", "{slug}/1-bundesliga.txt", 2010, app.SEASON_END_YEAR),
    "laliga": ("espana", "{slug}/1-liga.txt", 2012, app.SEASON_END_YEAR),
    "serie-a": ("italy", "{slug}/1-seriea.txt", 2013, app.SEASON_END_YEAR),
    "ligue-1": ("europe", "france/{slug}_fr1.txt", 2014, app.SEASON_END_YEAR),
    "tr-super-lig": ("europe", "turkey/{slug}_tr1.txt", 2018, app.SEASON_END_YEAR),
}

FOOTBALL_DATA_TR_SUPER_LIG_YEARS = [*range(2000, 2018), 2021, 2022]

FOOTBALL_DATA_TEAM_ALIASES = {
    "Ad. Demirspor": "Adana Demirspor",
    "Ankaragucu": "Ankaragücü",
    "Balikesirspor": "Balıkesirspor",
    "Basaksehir": "İstanbul Başakşehir",
    "Besiktas": "Beşiktaş",
    "Buyuksehyr": "İstanbul Başakşehir",
    "Diyarbakirspor": "Diyarbakırspor",
    "Elazigspor": "Elazığspor",
    "Erciyesspor": "Kayseri Erciyesspor",
    "Eskisehirspor": "Eskişehirspor",
    "Fatih Karagumruk": "Fatih Karagümrük",
    "Fenerbahce": "Fenerbahçe",
    "Gaziantep": "Gaziantep FK",
    "Genclerbirligi": "Gençlerbirliği",
    "Goztepe": "Göztepe",
    "Istanbul Basaksehir": "İstanbul Başakşehir",
    "Istanbulspor": "İstanbulspor",
    "Karabukspor": "Karabükspor",
    "Karagumruk": "Fatih Karagümrük",
    "Kasimpasa": "Kasımpaşa",
    "Mersin Idmanyurdu": "Mersin İdmanyurdu",
    "Osmanlispor": "Osmanlıspor",
    "Rizespor": "Çaykur Rizespor",
    "Umraniyespor": "Ümraniyespor",
}

EXTRA_SPLIT_TEXT_SOURCES = [
    ("uefa-champions-league", "champions-league", "{slug}/cl.txt", 2020, app.SEASON_END_YEAR),
    ("uefa-champions-league", "champions-league", "{slug}/clq.txt", 2020, app.SEASON_END_YEAR),
    ("uefa-europa-league", "champions-league", "{slug}/el.txt", 2011, app.SEASON_END_YEAR),
    ("uefa-europa-league", "champions-league", "{slug}/elq.txt", 2024, app.SEASON_END_YEAR),
    ("uefa-conference-league", "champions-league", "{slug}/conf.txt", 2021, app.SEASON_END_YEAR),
    ("uefa-conference-league", "champions-league", "{slug}/confq.txt", 2024, app.SEASON_END_YEAR),
]

INLINE_TEXT_SOURCES = [
    ("copa-america", "2011", "copa-america", "2011--argentina/copa.txt"),
    ("copa-america", "2015", "copa-america", "2015--chile/copa.txt"),
    ("copa-america", "2021", "copa-america", "2021--brazil/copa.txt"),
    ("copa-america", "2024", "copa-america", "2024--usa/copa.txt"),
    ("concacaf-gold-cup", "2011", "north-america-gold-cup", "2011--united-states/gold.txt"),
    ("concacaf-gold-cup", "2013", "north-america-gold-cup", "2013--united-states/gold.txt"),
]

SPLIT_JSON_SOURCES = {
    "uefa-champions-league": ("football.json", "{slug}/uefa.cl.json", 2010, app.SEASON_END_YEAR),
}

ANNUAL_JSON_SOURCES = {
    "copa-libertadores": ("football.json", "{year}/copa.l.json"),
}

EDITION_JSON_SOURCES = {
    "fifa-world-cup": ("worldcup.json", "{year}/worldcup.json"),
    "uefa-euro": ("euro.json", "{year}/euro.json"),
}


def season_slug(year: int) -> str:
    return f"{year}-{str(year + 1)[-2:]}"


def football_data_slug(year: int) -> str:
    return f"{str(year)[-2:]}{str(year + 1)[-2:]}"


def fetch_text(url: str) -> str | None:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=FETCH_TIMEOUT, context=SSL_CONTEXT) as response:
            return response.read().decode("utf-8-sig")
    except HTTPError as exc:
        if exc.code == 404:
            return None
        raise
    except URLError as exc:
        raise RuntimeError(f"could not fetch {url}: {exc}") from exc


def source_url(repo: str, path: str) -> str:
    return RAW_GITHUB.format(repo=repo, path=path)


def split_years(start_year: int, end_year: int):
    for year in range(start_year, end_year):
        yield year, app.season_label(year), season_slug(year)


def load_leagues(db):
    rows = db.execute("SELECT id, code, name, color FROM leagues").fetchall()
    return {row["code"]: row for row in rows}


def load_seasons(db):
    rows = db.execute("SELECT id, league_id, season FROM competition_seasons").fetchall()
    return {(row["league_id"], row["season"]): row["id"] for row in rows}


def external_id(league_code: str, season: str, match: ParsedMatch) -> str:
    raw = "|".join(
        [
            league_code,
            season,
            match.match_date,
            match.home_team.casefold().strip(),
            match.away_team.casefold().strip(),
        ]
    )
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:24]
    return f"b2b:{league_code}:{season}:{digest}"


def parse_json_matches(payload: str) -> list[ParsedMatch]:
    data = json.loads(payload)
    matches = []
    for item in data.get("matches", []):
        score = item.get("score") or {}
        full_time = score.get("ft") or []
        home_score = full_time[0] if len(full_time) >= 2 else None
        away_score = full_time[1] if len(full_time) >= 2 else None
        stage = item.get("group") or item.get("stage") or item.get("round") or ""
        matches.append(
            ParsedMatch(
                home_team=(item.get("team1") or "").strip(),
                away_team=(item.get("team2") or "").strip(),
                match_date=(item.get("date") or "").strip(),
                home_score=home_score,
                away_score=away_score,
                round_name=(item.get("round") or "").strip(),
                stage=stage.strip(),
                venue=(item.get("ground") or item.get("venue") or "").strip(),
            )
        )
    return [match for match in matches if match.home_team and match.away_team and match.match_date]


def infer_text_date(raw_date: str, start_year: int) -> str | None:
    match = re.search(r"([A-Z][a-z]{2})/(\d{1,2})", raw_date)
    if not match:
        return None
    month_name, day = match.groups()
    month = MONTHS.get(month_name)
    if not month:
        return None
    year = start_year if month >= 7 else start_year + 1
    try:
        return dt.date(year, month, int(day)).isoformat()
    except ValueError:
        return None


def parse_text_matches(payload: str, start_year: int) -> list[ParsedMatch]:
    matches = []
    current_date = None
    current_round = ""
    for raw_line in payload.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        round_label = stripped.lstrip("» ").strip()
        if round_label.startswith("Matchday") or round_label.startswith("Round"):
            current_round = round_label
            continue
        if stripped.startswith("[") and stripped.endswith("]"):
            current_date = infer_text_date(stripped, start_year)
            continue
        if re.match(r"^(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+[A-Z][a-z]{2}/\d{1,2}", stripped):
            current_date = infer_text_date(stripped, start_year)
            continue
        if not current_date:
            continue

        candidate = re.sub(r"^\d{1,2}\.\d{2}\s+", "", stripped)
        v_score_match = re.match(r"(.+?)\s+v\s+(.+?)\s+(\d+)-(\d+)(?:\s+\([^)]+\))?(?:\s+.*)?$", candidate)
        old_score_match = re.match(r"(.+?)\s+(\d+)-(\d+)(?:\s+\([^)]+\))?\s+(.+)$", candidate)
        v_fixture_match = re.match(r"(.+?)\s+v\s+(.+?)\s*$", candidate)
        if v_score_match:
            home, away, home_score, away_score = v_score_match.groups()
            home_score = int(home_score)
            away_score = int(away_score)
        elif old_score_match:
            home, home_score, away_score, away = old_score_match.groups()
            home_score = int(home_score)
            away_score = int(away_score)
        elif v_fixture_match:
            home, away = v_fixture_match.groups()
            home_score = None
            away_score = None
        else:
            continue
        away = re.sub(r"\s+\[[^\]]+\]$", "", away).strip()
        matches.append(
            ParsedMatch(
                home_team=home.strip(),
                away_team=away,
                match_date=current_date,
                home_score=home_score,
                away_score=away_score,
                round_name=current_round,
                venue="",
            )
        )
    return matches


def parse_annual_date(month_name: str, day: str, year: int) -> str | None:
    month = MONTHS.get(month_name)
    if not month:
        return None
    try:
        return dt.date(year, month, int(day)).isoformat()
    except ValueError:
        return None


def parse_inline_text_matches(payload: str, year: int) -> list[ParsedMatch]:
    matches = []
    current_round = ""
    for raw_line in payload.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("["):
            continue
        heading = stripped.split("|", 1)[0].strip()
        if not re.search(r"\d+-\d+", stripped):
            if heading and not heading.startswith("="):
                current_round = heading
            continue

        candidate = stripped.split("#", 1)[0].strip()
        candidate = re.sub(r"^\(\d+\)\s*", "", candidate)
        date_match = re.match(
            r"(?:(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+)?([A-Z][a-z]{2})/(\d{1,2})\s+\d{1,2}:\d{2}\s+(.+)$",
            candidate,
        )
        if not date_match:
            continue
        month_name, day, rest = date_match.groups()
        match_date = parse_annual_date(month_name, day, year)
        if not match_date:
            continue

        fixture, venue = rest, ""
        if "@" in fixture:
            fixture, venue = [part.strip() for part in fixture.split("@", 1)]

        penalty_match = re.match(r"(.+?)\s+(\d+)-(\d+)\s+pen\.\s+\((\d+)-(\d+)\)\s+(.+)$", fixture)
        normal_match = re.match(r"(.+?)\s+(\d+)-(\d+)(?:\s+a\.e\.t\.)?(?:\s+\([^)]+\))?\s+(.+)$", fixture)
        if penalty_match:
            home, _pen_home, _pen_away, home_score, away_score, away = penalty_match.groups()
        elif normal_match:
            home, home_score, away_score, away = normal_match.groups()
        else:
            continue

        matches.append(
            ParsedMatch(
                home_team=home.strip(),
                away_team=away.strip(),
                match_date=match_date,
                home_score=int(home_score),
                away_score=int(away_score),
                round_name=current_round,
                venue=venue,
            )
        )
    return matches


def football_data_team_name(value: str) -> str:
    name = str(value or "").strip()
    return FOOTBALL_DATA_TEAM_ALIASES.get(name, name)


def parse_football_data_date(value: str) -> str | None:
    raw_date = str(value or "").strip()
    for date_format in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return dt.datetime.strptime(raw_date, date_format).date().isoformat()
        except ValueError:
            continue
    return None


def parse_optional_int(value: str) -> int | None:
    raw_value = str(value or "").strip()
    if not raw_value:
        return None
    try:
        return int(raw_value)
    except ValueError:
        return None


def parse_football_data_matches(payload: str) -> list[ParsedMatch]:
    matches = []
    rows = csv.DictReader(io.StringIO(payload.lstrip("\ufeff")))
    for row in rows:
        match_date = parse_football_data_date(row.get("Date", ""))
        home_team = football_data_team_name(row.get("HomeTeam", ""))
        away_team = football_data_team_name(row.get("AwayTeam", ""))
        if not match_date or not home_team or not away_team:
            continue
        matches.append(
            ParsedMatch(
                home_team=home_team,
                away_team=away_team,
                match_date=match_date,
                home_score=parse_optional_int(row.get("FTHG", "")),
                away_score=parse_optional_int(row.get("FTAG", "")),
            )
        )
    return matches


def insert_teams(db, league_id: int, home_team: str, away_team: str):
    for team in (home_team, away_team):
        db.execute(
            "INSERT OR IGNORE INTO teams (league_id, name) VALUES (?, ?)",
            (league_id, team),
        )


def existing_match(db, league_id: int, season: str, match: ParsedMatch):
    return db.execute(
        """
        SELECT id, external_id
        FROM matches
        WHERE league_id = ?
          AND season = ?
          AND match_date = ?
          AND home_team = ?
          AND away_team = ?
        """,
        (league_id, season, match.match_date, match.home_team, match.away_team),
    ).fetchone()


def upsert_match(db, league, season_id: int | None, season: str, source: SourcePlan, match: ParsedMatch) -> str:
    league_id = league["id"]
    match_external_id = external_id(source.league_code, season, match)
    score_status = "finished" if match.home_score is not None and match.away_score is not None else "scheduled"
    competition = league["name"]
    summary = ""
    summary_en = ""
    venue = ""
    imported_at = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    duplicate = existing_match(db, league_id, season, match)
    if duplicate and not duplicate["external_id"]:
        db.execute(
            """
            UPDATE matches
            SET competition_season_id = ?,
                home_score = ?,
                away_score = ?,
                round_name = ?,
                stage = ?,
                status = ?,
                import_source = ?,
                external_id = ?,
                imported_at = ?,
                source_url = ?
            WHERE id = ?
            """,
            (
                season_id,
                match.home_score,
                match.away_score,
                match.round_name,
                match.stage,
                score_status,
                source.source_name,
                match_external_id,
                imported_at,
                source.source_url,
                duplicate["id"],
            ),
        )
        insert_teams(db, league_id, match.home_team, match.away_team)
        return "updated"

    existed = db.execute(
        "SELECT 1 FROM matches WHERE external_id = ?",
        (match_external_id,),
    ).fetchone()

    db.execute(
        """
        INSERT INTO matches (
            league_id, competition_season_id, home_team, away_team,
            competition, season, match_date, venue, summary, summary_en,
            source_url, home_score, away_score, round_name, stage, status,
            import_source, external_id, imported_at, poster_color
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(external_id) DO UPDATE SET
            competition_season_id = excluded.competition_season_id,
            venue = excluded.venue,
            summary = excluded.summary,
            summary_en = excluded.summary_en,
            source_url = excluded.source_url,
            home_score = excluded.home_score,
            away_score = excluded.away_score,
            round_name = excluded.round_name,
            stage = excluded.stage,
            status = excluded.status,
            import_source = excluded.import_source,
            imported_at = excluded.imported_at
        """,
        (
            league_id,
            season_id,
            match.home_team,
            match.away_team,
            competition,
            season,
            match.match_date,
            venue,
            summary,
            summary_en,
            source.source_url,
            match.home_score,
            match.away_score,
            match.round_name,
            match.stage,
            score_status,
            source.source_name,
            match_external_id,
            imported_at,
            league["color"],
        ),
    )
    insert_teams(db, league_id, match.home_team, match.away_team)
    return "updated" if existed else "inserted"


def record_import(db, source: SourcePlan, league_id: int | None, status: str, imported: int, updated: int, note: str = ""):
    db.execute(
        """
        INSERT INTO data_imports (
            source_name, source_url, league_id, season, status,
            imported_count, skipped_count, note
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (source.source_name, source.source_url, league_id, source.season, status, imported, updated, note),
    )


def update_season_status(db, league_id: int, season: str, source_url: str):
    db.execute(
        """
        UPDATE competition_seasons
        SET data_status = 'matches-imported',
            source_url = ?
        WHERE league_id = ?
          AND season = ?
        """,
        (source_url, league_id, season),
    )


def planned_sources(league_code: str | None = None) -> list[SourcePlan]:
    requested_league_code = league_code
    plans = []
    for start in FOOTBALL_DATA_TR_SUPER_LIG_YEARS:
        season = app.season_label(start)
        slug = football_data_slug(start)
        plans.append(
            SourcePlan(
                league_code="tr-super-lig",
                season=season,
                source_name="Football-Data CSV",
                source_url=FOOTBALL_DATA.format(slug=slug),
                parser="football-data-csv",
            )
        )

    for league_code, (repo, path_pattern, start_year, end_year) in TEXT_SOURCES.items():
        for start, season, slug in split_years(start_year, end_year):
            path = path_pattern.format(slug=slug)
            plans.append(
                SourcePlan(
                    league_code=league_code,
                    season=season,
                    source_name="OpenFootball text",
                    source_url=source_url(repo, path),
                    parser=f"text:{start}",
                )
            )

    for league_code, repo, path_pattern, start_year, end_year in EXTRA_SPLIT_TEXT_SOURCES:
        for start, season, slug in split_years(start_year, end_year):
            path = path_pattern.format(slug=slug)
            plans.append(
                SourcePlan(
                    league_code=league_code,
                    season=season,
                    source_name="OpenFootball text",
                    source_url=source_url(repo, path),
                    parser=f"text:{start}",
                )
            )

    for league_code, season, repo, path in INLINE_TEXT_SOURCES:
        plans.append(
            SourcePlan(
                league_code=league_code,
                season=season,
                source_name="OpenFootball text",
                source_url=source_url(repo, path),
                parser=f"inline-text:{season}",
            )
        )

    for league_code, (repo, path_pattern, start_year, end_year) in SPLIT_JSON_SOURCES.items():
        for _, season, slug in split_years(start_year, end_year):
            path = path_pattern.format(slug=slug)
            plans.append(
                SourcePlan(
                    league_code=league_code,
                    season=season,
                    source_name="OpenFootball JSON",
                    source_url=source_url(repo, path),
                    parser="json",
                )
            )

    for league_code, (repo, path_pattern) in ANNUAL_JSON_SOURCES.items():
        league = next(item for item in app.SEED_LEAGUES if item["code"] == league_code)
        for year in range(league.get("start_year", 2000), app.SEASON_END_YEAR + 1):
            path = path_pattern.format(year=year)
            plans.append(
                SourcePlan(
                    league_code=league_code,
                    season=str(year),
                    source_name="OpenFootball JSON",
                    source_url=source_url(repo, path),
                    parser="json",
                )
            )

    for league_code, (repo, path_pattern) in EDITION_JSON_SOURCES.items():
        league = next(item for item in app.SEED_LEAGUES if item["code"] == league_code)
        for year in league.get("editions", []):
            path = path_pattern.format(year=year)
            plans.append(
                SourcePlan(
                    league_code=league_code,
                    season=str(year),
                    source_name="OpenFootball JSON",
                    source_url=source_url(repo, path),
                    parser="json",
                )
            )
    if requested_league_code:
        plans = [source for source in plans if source.league_code == requested_league_code]
    return plans


def import_source(db, source: SourcePlan, leagues, seasons, dry_run=False):
    league = leagues.get(source.league_code)
    if not league:
        record_import(db, source, None, "missing-league", 0, 0, "league code is not in the local database")
        return 0, 0, "missing-league"

    payload = fetch_text(source.source_url)
    if payload is None:
        record_import(db, source, league["id"], "missing-source", 0, 0, "source file not available")
        return 0, 0, "missing-source"

    if source.parser == "json":
        parsed = parse_json_matches(payload)
    elif source.parser == "football-data-csv":
        parsed = parse_football_data_matches(payload)
    elif source.parser.startswith("inline-text:"):
        parsed = parse_inline_text_matches(payload, int(source.parser.split(":", 1)[1]))
    else:
        parsed = parse_text_matches(payload, int(source.parser.split(":", 1)[1]))

    if dry_run:
        record_import(db, source, league["id"], "dry-run", len(parsed), 0, "not written")
        return len(parsed), 0, "dry-run"

    season_id = seasons.get((league["id"], source.season))
    inserted = 0
    updated = 0
    for match in parsed:
        result = upsert_match(db, league, season_id, source.season, source, match)
        if result == "inserted":
            inserted += 1
        else:
            updated += 1
    if parsed:
        update_season_status(db, league["id"], source.season, source.source_url)
        status = "imported"
        note = f"{len(parsed)} matches parsed"
    else:
        status = "empty-source"
        note = "source fetched but no matches parsed"
    record_import(db, source, league["id"], status, inserted, updated, note)
    return inserted, updated, status


def import_all(dry_run=False, league_code: str | None = None):
    app.init_db()
    plans = planned_sources(league_code=league_code)
    totals = {"inserted": 0, "updated": 0, "imported_sources": 0, "missing_sources": 0}
    with app.connect_db() as db:
        leagues = load_leagues(db)
        seasons = load_seasons(db)
        for source in plans:
            inserted, updated, status = import_source(db, source, leagues, seasons, dry_run=dry_run)
            totals["inserted"] += inserted
            totals["updated"] += updated
            if status in {"imported", "dry-run"}:
                totals["imported_sources"] += 1
                print(f"{status}: {source.league_code} {source.season} +{inserted} ~{updated}")
            elif status == "missing-source":
                totals["missing_sources"] += 1
        if not dry_run:
            app.rebuild_match_search(db)
        db.commit()
    return totals


def main():
    parser = argparse.ArgumentParser(description="Import OpenFootball match data into box-to-boxd.")
    parser.add_argument("--dry-run", action="store_true", help="fetch and parse without writing matches")
    parser.add_argument("--league-code", help="only import sources for one local league code")
    args = parser.parse_args()
    totals = import_all(dry_run=args.dry_run, league_code=args.league_code)
    print(
        "done: "
        f"{totals['inserted']} inserted, "
        f"{totals['updated']} updated, "
        f"{totals['imported_sources']} sources imported, "
        f"{totals['missing_sources']} sources missing"
    )


if __name__ == "__main__":
    main()
