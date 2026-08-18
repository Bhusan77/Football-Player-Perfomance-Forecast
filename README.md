# Data Scout — Day 5 capstone (standalone)

Run the Day 5 interactive lab **locally, with no database** — and get the
**exact same numbers *and* the exact same UI** as the course. This bundles the
real course lab (the React `ScoutBuilderLab` and its components) into a static
`app.js`/`app.css` and serves it from a small FastAPI server backed by the real
course engine over a CSV snapshot of the data. No Node needed to run it — the UI
is pre-built.

## Run it

```bash
pip install -r requirements.txt
python api_server.py
# open http://localhost:8000
```

That's it. `data/players.csv.gz` + `data/supplementary.csv.gz` are loaded on
startup into an in-memory SQLite database.

## What's in here

| File | What it is |
|---|---|
| `api_server.py` | FastAPI server: loads the CSVs, serves the bundled lab (`app.js`/`app.css`) + the `/api/data-scout` command API + `/upload` + `/status`. |
| `scout_engine.py` | The **course engine, verbatim**, with its database credentials removed. All its DB access goes through `get_connection()`, which `api_server.py` overrides to point at the local SQLite store — so every command (composite index, similarity + AHP/TOPSIS, the 7 gem signals, market-value heuristic, career history) runs unchanged. |
| `index.html` | Thin shell: the upload panel + a `#root` div where the lab mounts. |
| `app.js`, `app.css` | The **real Day-5 course lab, pre-built** — `ScoutBuilderLab` and its components (profile + radar, similar players with the AHP/TOPSIS popup, 3-way career-trajectory compare, Hidden Gems with the inline row-expand). Same code as the live course. |
| `web/` | The build inputs (`main.tsx` entry, `app.css` Tailwind input, `tailwind.config.js`). Only needed if you want to rebuild the bundle — see below. |
| `data/*.csv.gz` | Gzipped CSV snapshot of the two tables the engine reads (`league_season_team_player_data`, `player_supplementary_data`). |
| `requirements.txt` | pandas, numpy, scipy, scikit-learn, fastapi, uvicorn. |
| `CODE_EXPLAINED.pdf` / `.md` | The **complete annotated source**: `api_server.py` and the whole engine (`scout_engine.py`), every block shown as real code with a plain-English note on what it does and how it works (composite index, AHP+TOPSIS, the 7 hidden-gem signals, market value, and more). Regenerate with `web/build_code_explained.py` + `web/gen_pdf.py`. |

## Rebuilding the UI bundle (optional)

`app.js`/`app.css` are checked in, so you don't need Node to *run* the lab. To
rebuild them from the course components (run from the **course repo root**, which
has the `node_modules` and the `src/components/Scout*.tsx` source):

```bash
node_modules/.bin/tailwindcss -c data-scout-lab/web/tailwind.config.js \
  -i data-scout-lab/web/app.css -o data-scout-lab/app.css --minify
node_modules/.bin/esbuild data-scout-lab/web/main.tsx --bundle --minify \
  --format=iife --jsx=automatic --tsconfig=tsconfig.json \
  --define:process.env.NODE_ENV='"production"' --outfile=data-scout-lab/app.js
```

## Why the results match

The engine is the same code the live lab calls. Only the **data layer** is
swapped: instead of PostgreSQL, `get_connection()` returns a shim over an
in-memory SQLite database loaded from the CSVs (the queries are standard SQL, so
they run as-is; `%s` placeholders are translated to `?`). Nothing in the scoring
logic changes, so the composite index, similarity ranking, hidden-gem signals and
market values are identical to the course.

## Uploading data

If the server prints *"No data/…found"* (the `data/` folder wasn't next to
`api_server.py`), or you want a different export, use the **Data snapshot** panel
at the top of the web UI — you can upload each file **separately** (each one
replaces just its own table).

Or from the command line — either file on its own, or both:

```bash
curl -F players=@players.csv.gz http://localhost:8000/upload
curl -F supplementary=@supplementary.csv.gz http://localhost:8000/upload
```

`GET /status` reports how many rows are currently loaded. The CSVs must have the
same columns as the shipped ones (a full dump of the two tables).

## The API directly

Every command the lab uses is available at `POST /api/data-scout` with a JSON
body `{ "command": "...", ... }`, e.g.:

```bash
curl -s http://localhost:8000/api/data-scout -H 'Content-Type: application/json' \
  -d '{"command":"get_player_profile","season":"2024-2025","league":"la-liga","team":"Real Madrid","player":"Jude Bellingham"}'
```

Commands: `get_leagues`, `get_teams`, `get_players`, `get_player_profile`,
`get_similar_players`, `compare_players`, `get_hidden_gems`, `get_market_value`,
`get_moneyball_score`, `get_career_history`, and more (see `scout_engine.COMMANDS`).

## Note

The in-memory database is ~400 MB uncompressed, so expect ~1 GB of RAM while
running. Startup takes a few seconds to load the CSVs.
