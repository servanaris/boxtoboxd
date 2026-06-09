# box-to-boxd

box-to-boxd is a small Letterboxd-style football app built with beginner-friendly Python and SQLite.

You can:

- browse a catalog of football matches
- switch between Turkish and English UI
- create an account
- rate and review matches
- keep a personal diary
- save matches to a watchlist
- submit missing real matches for admin review
- optionally log a submitted match so the review is posted automatically after approval
- approve submitted matches as the first/admin user
- browse a source-indexed organization database for domestic leagues, international cups, and continental club tournaments
- see a rotating classics section instead of the same fixed list every visit

## Run it

```bash
python3 app.py
```

Then open:

```text
http://127.0.0.1:8000
```

The repo includes a sanitized catalog database at `data/box_to_boxd.sqlite3` so a fresh clone opens with match data already loaded. If the old local `data/matchboxd.sqlite3` file already exists, the app reuses it so early private local data is not lost.

## Run tests

```bash
python3 -m unittest discover -s tests
```

## Deploy from GitHub

GitHub Pages cannot run this app because box-to-boxd is a Python server with SQLite, accounts, reviews, and moderation. Use a GitHub-connected web host instead.

This repo includes `render.yaml` for Render:

1. Push the repo to GitHub.
2. Open [Render Blueprints](https://dashboard.render.com/blueprints/new).
3. Connect the `servanaris/boxtoboxd` GitHub repo.
4. Create the `boxtoboxd` web service from the blueprint.
5. Render will run the tests during build and start the app with `python3 app.py`.

The free Render web service is good for a public demo. It uses the included catalog database, but free instances have an ephemeral filesystem, so new signups/reviews can reset after redeploys, restarts, or idle spin-downs. For a real production launch, move user data to Postgres or attach a persistent disk on a paid service.

## Project shape

```text
app.py              # Python server, routes, database setup, i18n, and page rendering
static/styles.css   # Visual styling
tests/test_app.py   # Small standard-library test suite
data/box_to_boxd.sqlite3 # Sanitized seed catalog database
render.yaml         # Render deployment blueprint
```

## Admin flow

The first account created becomes the admin account. Normal users submit missing matches from the `log` page with a source link. The admin can review pending submissions on the `moderation` page and approve real matches into the catalog.

If a user checks the optional log box during submission, their rating, watched date, and review text are stored with the pending submission. When the admin approves the match, the review is posted automatically.

## Data scope

The app seeds:

- Trendyol Süper Lig and the five big European leagues
- FIFA World Cup
- UEFA EURO, Copa América, Africa Cup of Nations, AFC Asian Cup, Concacaf Gold Cup, and OFC Nations Cup
- UEFA Champions League, UEFA Europa League, UEFA Conference League, Copa Libertadores, AFC Champions League Elite, and Concacaf Champions Cup

For those organizations, `competition_seasons` stores source-indexed season rows from 2000/01 onward where the competition existed. The included seed database also contains imported match rows for the supported public sources currently wired into `tools/import_openfootball_data.py`, including expanded Turkish Süper Lig coverage.

## Why no framework yet?

This version intentionally uses only Python's standard library. That means you do not need Flask, Django, Node, or any package manager before you can run it.

Once the idea feels right, the natural next step is moving this into Flask or Django so it can grow into a production app with proper templates, migrations, follows, likes, comments, and deployment.
