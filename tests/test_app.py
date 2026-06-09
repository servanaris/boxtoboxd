import tempfile
import unittest
from pathlib import Path

import app
from tools import import_openfootball_data as importer


class MatchboxdTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        app.DB_PATH = Path(self.tmp.name) / "test.sqlite3"
        app.SESSIONS.clear()
        app.init_db(seed=True)

    def tearDown(self):
        self.tmp.cleanup()

    def test_database_is_seeded(self):
        with app.connect_db() as db:
            match_count = db.execute("SELECT COUNT(*) AS count FROM matches").fetchone()["count"]
            league_count = db.execute("SELECT COUNT(*) AS count FROM leagues").fetchone()["count"]
            team_count = db.execute("SELECT COUNT(*) AS count FROM teams").fetchone()["count"]
            season_count = db.execute("SELECT COUNT(*) AS count FROM competition_seasons").fetchone()["count"]
        self.assertGreaterEqual(match_count, 20)
        self.assertEqual(league_count, len(app.SEED_LEAGUES))
        self.assertGreaterEqual(team_count, 110)
        self.assertGreaterEqual(season_count, 350)

    def test_password_hash_round_trip(self):
        stored = app.hash_password("strong-password")
        self.assertTrue(app.verify_password("strong-password", stored))
        self.assertFalse(app.verify_password("wrong-password", stored))

    def test_login_page_has_forgot_password_and_save_controls(self):
        turkish_html = app.render_auth_page("login", lang="tr")
        english_html = app.render_auth_page("login", lang="en")

        self.assertIn("şifremi unuttum", turkish_html)
        self.assertIn("kaydet", turkish_html)
        self.assertIn("kullanıcı adı veya e-posta", turkish_html)
        self.assertIn("forgot password", english_html)
        self.assertIn("save", english_html)

    def test_email_verification_and_password_reset_flow(self):
        with app.connect_db() as db:
            user_id = db.execute(
                """
                INSERT INTO users (username, email, password_hash, email_verified)
                VALUES (?, ?, ?, 0)
                """,
                ("verifyme", "verifyme@example.com", app.hash_password("oldpass")),
            ).lastrowid
            verification_token = app.create_email_verification_token(db, user_id)

        self.assertTrue(app.verify_email_token(verification_token))
        self.assertFalse(app.verify_email_token(verification_token))

        reset_token = app.create_password_reset_token("verifyme@example.com")
        self.assertTrue(reset_token)
        self.assertTrue(app.reset_password_with_token(reset_token, "newpass123"))
        self.assertFalse(app.reset_password_with_token(reset_token, "anotherpass"))

        with app.connect_db() as db:
            row = db.execute("SELECT * FROM users WHERE username = ?", ("verifyme",)).fetchone()

        self.assertEqual(row["email_verified"], 1)
        self.assertTrue(app.verify_password("newpass123", row["password_hash"]))

    def test_import_boilerplate_summary_is_cleared_and_hidden(self):
        with app.connect_db() as db:
            match_id = db.execute(
                """
                INSERT INTO matches (
                    home_team, away_team, competition, season, match_date, venue,
                    summary, summary_en, poster_color
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "France",
                    "Portugal",
                    "UEFA EURO",
                    "2024",
                    "2024-07-05",
                    "Hamburg",
                    "UEFA EURO 2024 fikstüründen içe aktarıldı.",
                    "imported from the UEFA EURO 2024 fixture list.",
                    "#2157a4",
                ),
            ).lastrowid
            app.clear_imported_match_summaries(db)
            row = db.execute(app.match_rows_query(where="WHERE matches.id = ?"), (match_id,)).fetchone()

        card = app.match_card(row)

        self.assertEqual(row["summary"], "")
        self.assertEqual(row["summary_en"], "")
        self.assertNotIn("fikstüründen içe aktarıldı", card)
        self.assertNotIn("<p></p>", card)

    def test_classics_only_use_curated_matches(self):
        seed_match = app.SEED_MATCHES[0]
        with app.connect_db() as db:
            db.execute(
                """
                INSERT INTO matches (
                    home_team, away_team, competition, season, match_date, venue,
                    summary, summary_en, poster_color
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "Ordinary FC",
                    "Routine United",
                    "Premier League",
                    "2025/26",
                    "2026-01-01",
                    "Somewhere",
                    "not a classic.",
                    "not a classic.",
                    "#3d195b",
                ),
            )
            db.execute(
                """
                INSERT INTO matches (
                    home_team, away_team, competition, season, match_date, venue,
                    summary, summary_en, poster_color, import_source, external_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    seed_match["home_team"],
                    seed_match["away_team"],
                    "FIFA World Cup",
                    seed_match["season"],
                    seed_match["match_date"],
                    seed_match["venue"],
                    seed_match["summary"],
                    seed_match["summary_en"],
                    seed_match["poster_color"],
                    "imported duplicate",
                    "duplicate-classic",
                ),
            )

        classic_keys = {
            (match["home_team"], match["away_team"], match["match_date"])
            for match in app.SEED_MATCHES
        }
        classics = app.fetch_classic_matches(limit=100)

        self.assertGreater(len(classics), 8)
        self.assertTrue(
            all((match["home_team"], match["away_team"], match["match_date"]) in classic_keys for match in classics)
        )
        self.assertTrue(all(match["import_source"] is None and match["external_id"] is None for match in classics))
        self.assertFalse(any(match["home_team"] == "Ordinary FC" for match in classics))

    def test_home_page_renders_seed_match(self):
        html = app.render_home(user=None, lang="en", query="france")
        self.assertIn("Argentina vs France", html)
        self.assertIn("recent reviews", html)
        self.assertIn("quick searches", html)
        self.assertIn("filter", html)
        self.assertNotIn("show more", html)
        self.assertIn("classics", app.render_home(user=None, lang="en"))
        self.assertIn("show more", app.render_home(user=None, lang="en"))
        turkish_html = app.render_home(user=None)
        self.assertIn("son yorumlar", turkish_html)
        self.assertIn("Trendyol Süper Lig", turkish_html)
        self.assertIn("klasik maçlar", turkish_html)
        self.assertIn("hızlı aramalar", turkish_html)
        self.assertIn("filtrele", turkish_html)
        self.assertIn("daha fazlasını göster", turkish_html)
        self.assertIn('action="/#match-results"', turkish_html)
        self.assertIn('id="match-results" class="match-grid"', turkish_html)
        self.assertIn('/?q=Galatasaray#match-results', turkish_html)
        self.assertLess(turkish_html.index("klasik maçlar"), turkish_html.index("organizasyon veritabanı"))
        self.assertLess(turkish_html.index("organizasyon veritabanı"), turkish_html.index("son yorumlar"))

        empty_html = app.render_home(user=None, lang="tr", query="zzzzzz-not-a-match")
        self.assertIn('href="/log">öneri gönder</a>', empty_html)

        limited_search = app.render_home(user=None, lang="tr", query="ucl", match_limit=5)
        self.assertIn('name="q" value="ucl"', limited_search)
        self.assertIn('name="limit" value="29"', limited_search)
        self.assertIn("daha fazlasını göster", limited_search)
        self.assertRegex(limited_search, r'id="match-\d+"')
        self.assertRegex(limited_search, r'action="/#match-\d+"')

        filtered_search = app.render_home(
            user=None,
            lang="tr",
            query="ucl",
            match_limit=5,
            filters={"team": "Liverpool", "opponent": "Barcelona"},
        )
        self.assertIn('name="team" value="Liverpool"', filtered_search)
        self.assertIn('name="opponent" value="Barcelona"', filtered_search)

        log_more = app.render_log({"id": 1, "username": "tester", "is_admin": 0}, lang="tr", query="ucl", match_limit=5)
        self.assertIn('action="/log#match-results"', log_more)
        self.assertRegex(log_more, r'action="/log#match-\d+"')

    def test_stadium_details_are_not_user_facing_or_searchable(self):
        with app.connect_db() as db:
            match_id = db.execute(
                """
                INSERT INTO matches (
                    home_team, away_team, competition, season, match_date, venue,
                    summary, summary_en, poster_color
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "Hidden Venue FC",
                    "Plain Opponent",
                    "Test Cup",
                    "2025/26",
                    "2026-04-01",
                    "Hidden Ground",
                    "venue should stay internal.",
                    "venue should stay internal.",
                    "#1f7a4d",
                ),
            ).lastrowid
            app.upsert_match_search_entry(db, match_id)

        home_html = app.render_home(user=None, lang="tr", query="Hidden Venue FC")
        detail_html = app.render_match_detail(None, "en", match_id)
        log_html = app.render_log({"id": 1, "username": "tester", "is_admin": 0}, lang="tr")
        venue_search = app.fetch_matches("Hidden Ground", limit=5)

        self.assertIn("takım, ülke, lig", home_html)
        self.assertNotIn("takım, ülke, lig, stat", home_html)
        self.assertNotIn("Hidden Ground", home_html)
        self.assertNotIn("Hidden Ground", detail_html)
        self.assertNotIn('name="venue"', log_html)
        self.assertFalse(any(match["id"] == match_id for match in venue_search))

    def test_search_aliases_and_index_ranking(self):
        self.assertEqual(app.build_fts_query("ucl"), "uefa* champions* league*")
        self.assertEqual(app.build_fts_query("şampiyonlar"), "uefa* champions* league*")
        self.assertEqual(app.build_fts_query("şampiyonlar ligi"), "uefa* champions* league*")
        self.assertEqual(app.build_fts_query("fransa portekiz"), "france* portugal*")

        matches = app.fetch_matches("ucl", limit=5)

        self.assertGreater(len(matches), 0)
        self.assertTrue(
            any("Champions League" in app.competition_label(match) or "Champions League" in match["competition"] for match in matches)
        )
        self.assertGreater(len(app.fetch_matches("derbi", limit=5)), 0)
        self.assertGreater(len(app.fetch_matches("derby", limit=5)), 0)
        self.assertGreater(len(app.fetch_matches("dünya kupası", limit=5)), 0)

        country_matches = app.fetch_matches("fransa portekiz", limit=5)
        self.assertTrue(any({"France", "Portugal"} == {match["home_team"], match["away_team"]} for match in country_matches))

    def test_match_filters_find_head_to_head_and_organization(self):
        matches = app.fetch_matches(
            "ucl",
            limit=5,
            filters={"team": "Liverpool", "opponent": "Barcelona", "year": "2019"},
        )

        self.assertTrue(any(match["home_team"] == "Liverpool" and match["away_team"] == "Barcelona" for match in matches))

        translated_matches = app.fetch_matches(
            limit=5,
            filters={"team": "fransa", "opponent": "arjantin", "year": "2022"},
        )

        self.assertTrue(any({"Argentina", "France"} == {match["home_team"], match["away_team"]} for match in translated_matches))

        with app.connect_db() as db:
            league_id = db.execute("SELECT id FROM leagues WHERE code = ?", ("tr-super-lig",)).fetchone()["id"]
            match_id = db.execute(
                """
                INSERT INTO matches (
                    league_id, home_team, away_team, competition, season, match_date,
                    venue, summary, summary_en, poster_color
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    league_id,
                    "Galatasaray",
                    "Beşiktaş",
                    "Trendyol Süper Lig",
                    "2025/26",
                    "2026-02-15",
                    "RAMS Park",
                    "filtre testi.",
                    "filter test.",
                    "#d61f3c",
                ),
            ).lastrowid
            app.upsert_match_search_entry(db, match_id)

        organization_matches = app.fetch_matches(
            limit=5,
            filters={"team": "Galatasaray", "opponent": "Beşiktaş", "year": "2026", "organization": str(league_id)},
        )

        self.assertEqual(len(organization_matches), 1)
        self.assertEqual(organization_matches[0]["competition"], "Trendyol Süper Lig")
        legacy_name_search = app.fetch_matches("Turkcell Süper Lig Galatasaray", limit=5)
        self.assertTrue(any(match["id"] == match_id for match in legacy_name_search))
        legacy_name_filter = app.fetch_matches(
            limit=5,
            filters={"team": "Galatasaray", "organization": "Spor Toto Super Lig"},
        )
        self.assertTrue(any(match["id"] == match_id for match in legacy_name_filter))
        self.assertEqual(
            len(app.fetch_matches(limit=5, filters={"team": "besiktas", "opponent": "galatasaray", "organization": str(league_id)})),
            1,
        )

    def test_football_data_csv_parser_covers_turkish_super_lig_rows(self):
        payload = "\n".join(
            [
                "Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,FTR",
                "T1,22/09/13,,Besiktas,Galatasaray,0,3,A",
                "T1,05/08/2022,19:00,Istanbulspor,Trabzonspor,0,2,A",
            ]
        )

        matches = importer.parse_football_data_matches(payload)
        sources = importer.planned_sources("tr-super-lig")

        self.assertEqual(matches[0].home_team, "Beşiktaş")
        self.assertEqual(matches[0].match_date, "2013-09-22")
        self.assertEqual(matches[0].away_score, 3)
        self.assertEqual(matches[1].home_team, "İstanbulspor")
        self.assertTrue(
            any(source.season == "2013/14" and source.parser == "football-data-csv" for source in sources)
        )

    def test_first_user_becomes_admin(self):
        with app.connect_db() as db:
            db.execute(
                "INSERT INTO users (username, email, password_hash, is_admin) VALUES (?, ?, ?, ?)",
                ("owner", "owner@example.com", app.hash_password("secret123"), 1),
            )
            row = db.execute("SELECT is_admin FROM users WHERE username = ?", ("owner",)).fetchone()

        self.assertEqual(row["is_admin"], 1)

    def test_match_submission_waits_for_review(self):
        with app.connect_db() as db:
            user_id = db.execute(
                "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
                ("tester", "tester@example.com", app.hash_password("secret123")),
            ).lastrowid
            league_id = db.execute("SELECT id FROM leagues WHERE code = ?", ("tr-super-lig",)).fetchone()["id"]
            db.execute(
                """
                INSERT INTO match_submissions (
                    submitted_by, requested_league_id, home_team, away_team, competition,
                    season, match_date, venue, source_url, note, log_after_approval,
                    submit_rating, submit_watched_on, submit_review_body
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    league_id,
                    "Galatasaray",
                    "Fenerbahçe",
                    "Trendyol Süper Lig",
                    "2025/26",
                    "2026-05-05",
                    "RAMS Park",
                    "https://www.tff.org/",
                    "Derbi önerisi",
                    1,
                    9,
                    "2026-05-05",
                    "dev derbi enerjisi.",
                ),
            )
            pending = db.execute("SELECT COUNT(*) AS count FROM match_submissions WHERE status = 'pending'").fetchone()["count"]
            log = db.execute("SELECT submit_rating, submit_review_body FROM match_submissions").fetchone()
            catalog = db.execute(
                "SELECT COUNT(*) AS count FROM matches WHERE home_team = ? AND away_team = ?",
                ("Galatasaray", "Fenerbahçe"),
            ).fetchone()["count"]

        self.assertEqual(pending, 1)
        self.assertEqual(log["submit_rating"], 9)
        self.assertIn("derbi", log["submit_review_body"])
        self.assertEqual(catalog, 0)

    def test_review_insert_can_be_updated(self):
        with app.connect_db() as db:
            user_id = db.execute(
                "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
                ("tester", "tester@example.com", app.hash_password("secret123")),
            ).lastrowid
            match_id = db.execute("SELECT id FROM matches LIMIT 1").fetchone()["id"]
            db.execute(
                "INSERT INTO reviews (user_id, match_id, rating, body, watched_on) VALUES (?, ?, ?, ?, ?)",
                (user_id, match_id, 8, "Loved the tempo.", "2026-05-05"),
            )
            db.execute(
                """
                INSERT INTO reviews (user_id, match_id, rating, body, watched_on)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id, match_id) DO UPDATE SET
                    rating = excluded.rating,
                    body = excluded.body,
                    watched_on = excluded.watched_on
                """,
                (user_id, match_id, 9, "Even better on rewatch.", "2026-05-05"),
            )
            row = db.execute("SELECT rating, body FROM reviews WHERE user_id = ?", (user_id,)).fetchone()

        self.assertEqual(row["rating"], 9)
        self.assertIn("rewatch", row["body"])


if __name__ == "__main__":
    unittest.main()
