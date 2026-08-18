"""
Data Scout - Day 5 capstone, standalone.

Runs the EXACT same engine as the live course lab, but over a local CSV snapshot
instead of a database.

Includes:
- Data Scout
- Player analysis
- Similar players
- Skill Ranking Forecast
- Model Evaluation
- Cross-Validation
- Light / Dark theme for the entire application
"""

import io
import json
import os
import sqlite3
import threading

import pandas as pd
from fastapi import FastAPI, File, Query, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse

import scout_engine as eng


# ==============================================================================
# PATHS / DATABASE
# ==============================================================================

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "data")

_LOCK = threading.Lock()

_db = sqlite3.connect(
    ":memory:",
    check_same_thread=False
)


# ==============================================================================
# SQLITE / PSYCOPG2 SHIM
# ==============================================================================

class _Cur:

    def __init__(self, cur):
        self._cur = cur

    def execute(self, sql, params=None):
        sql = sql.replace("%s", "?")
        self._cur.execute(
            sql,
            list(params) if params else []
        )
        return self

    def fetchall(self):
        return self._cur.fetchall()

    def fetchone(self):
        return self._cur.fetchone()

    @property
    def description(self):
        return self._cur.description

    def close(self):
        self._cur.close()


class _Conn:

    def cursor(self):
        return _Cur(_db.cursor())

    def execute(self, sql, params=None):
        return self.cursor().execute(sql, params)

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        # Keep shared in-memory database alive.
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass


eng.get_connection = lambda: _Conn()


# ==============================================================================
# CACHE
# ==============================================================================

def _clear_caches():

    for name in (
        "_ALL_LEAGUES_CACHE",
        "_MS_POOL_CACHE"
    ):

        c = getattr(eng, name, None)

        if isinstance(c, dict):
            c.clear()


# ==============================================================================
# LOAD DATA
# ==============================================================================

def load_players_frame(players: pd.DataFrame):

    with _LOCK:

        players.to_sql(
            "league_season_team_player_data",
            _db,
            if_exists="replace",
            index=False
        )

        cur = _db.cursor()

        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS ix_season
            ON league_season_team_player_data(season)
            """
        )

        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS ix_season_league
            ON league_season_team_player_data(season, league)
            """
        )

        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS ix_player
            ON league_season_team_player_data(player)
            """
        )

        _db.commit()

        _clear_caches()


def load_supp_frame(supplementary: pd.DataFrame):

    with _LOCK:

        supplementary.to_sql(
            "player_supplementary_data",
            _db,
            if_exists="replace",
            index=False
        )

        cur = _db.cursor()

        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS ix_supp_player
            ON player_supplementary_data(player)
            """
        )

        _db.commit()

        _clear_caches()


def load_frames(
    players: pd.DataFrame,
    supplementary: pd.DataFrame
):

    load_players_frame(players)
    load_supp_frame(supplementary)


def _read_csv(
    raw: bytes,
    name: str
) -> pd.DataFrame:

    gz = name.endswith(".gz")

    return pd.read_csv(
        io.BytesIO(raw),
        compression="gzip" if gz else None,
        low_memory=False
    )


def _boot():

    players = os.path.join(
        DATA_DIR,
        "players.csv.gz"
    )

    supp = os.path.join(
        DATA_DIR,
        "supplementary.csv.gz"
    )

    if os.path.exists(players) and os.path.exists(supp):

        p = pd.read_csv(
            players,
            compression="gzip",
            low_memory=False
        )

        s = pd.read_csv(
            supp,
            compression="gzip",
            low_memory=False
        )

        load_frames(p, s)

        print(
            f"Loaded {len(p):,} player-season rows + "
            f"{len(s):,} supplementary rows."
        )

    else:

        print(
            "No data/players.csv.gz + data/supplementary.csv.gz found - "
            "upload a snapshot via POST /upload."
        )


_boot()


# ==============================================================================
# FASTAPI
# ==============================================================================

app = FastAPI(
    title="Data Scout - Day 5 capstone (standalone)"
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==============================================================================
# JSON HELPER
# ==============================================================================

def _json(result) -> Response:

    return Response(
        json.dumps(
            result,
            default=str
        ),
        media_type="application/json"
    )


# ==============================================================================
# DATA SCOUT API
# ==============================================================================

@app.post("/api/data-scout")
async def data_scout(request: Request):

    body = await request.json()

    fn = eng.COMMANDS.get(
        body.get("command", "")
    )

    if fn is None:

        return _json({
            "error":
            f"unknown command: {body.get('command')}"
        })

    with _LOCK:

        try:

            return _json(
                fn(body)
            )

        except Exception as e:

            return _json({
                "error": str(e)
            })


# ==============================================================================
# UPLOAD
# ==============================================================================

@app.post("/upload")
async def upload(
    players: UploadFile = File(None),
    supplementary: UploadFile = File(None)
):

    out = {
        "ok": True
    }

    if players is not None:

        p = _read_csv(
            await players.read(),
            players.filename
        )

        load_players_frame(p)

        out["player_rows"] = len(p)

    if supplementary is not None:

        s = _read_csv(
            await supplementary.read(),
            supplementary.filename
        )

        load_supp_frame(s)

        out["supplementary_rows"] = len(s)

    if (
        "player_rows" not in out
        and
        "supplementary_rows" not in out
    ):

        return _json({
            "ok": False,
            "error": "no file provided"
        })

    return out


# ==============================================================================
# STATIC FILES
# ==============================================================================

@app.get("/app.js")
def app_js():

    return FileResponse(
        os.path.join(HERE, "app.js"),
        media_type="text/javascript"
    )


@app.get("/app.css")
def app_css():

    return FileResponse(
        os.path.join(HERE, "app.css"),
        media_type="text/css"
    )


# ==============================================================================
# SHORTLIST
# ==============================================================================

@app.get("/api/data-scout/shortlist")
def shortlist_get():

    return {}


@app.post("/api/data-scout/shortlist")
async def shortlist_post(request: Request):

    try:
        await request.json()

    except Exception:
        pass

    return {
        "ok": True
    }


# ==============================================================================
# STATUS
# ==============================================================================

@app.get("/status")
def status():

    def _count(tbl):

        try:

            with _LOCK:

                return _db.execute(
                    f"SELECT COUNT(*) FROM {tbl}"
                ).fetchone()[0]

        except Exception:

            return 0

    return {
        "player_rows":
            _count(
                "league_season_team_player_data"
            ),

        "supplementary_rows":
            _count(
                "player_supplementary_data"
            )
    }


# ==============================================================================
# FORECAST LINK
# ==============================================================================

_FORECAST_LINK_HTML = """
<a
    href="/forecast"
    style="
        position:fixed;
        top:12px;
        right:16px;
        z-index:9999;
        background:#2952a3;
        color:#fff;
        padding:8px 14px;
        border-radius:6px;
        font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;
        font-size:13px;
        font-weight:600;
        text-decoration:none;
        box-shadow:0 2px 6px rgba(0,0,0,.15);
    "
>
    Skill Ranking Forecast &rarr;
</a>
"""


# ==============================================================================
# DATA SCOUT HOME
# ==============================================================================

@app.get("/")
def index():

    idx = os.path.join(
        HERE,
        "index.html"
    )

    if os.path.exists(idx):

        with open(
            idx,
            "r",
            encoding="utf-8"
        ) as f:

            html = f.read()

        if "</body>" in html:

            html = html.replace(
                "</body>",
                _FORECAST_LINK_HTML +
                "</body>"
            )

        else:

            html += _FORECAST_LINK_HTML

        return HTMLResponse(html)

    return HTMLResponse(
        "<h1>Data Scout API</h1>"
        "<p>POST /api/data-scout</p>"
    )


# ==============================================================================
# ML FORECAST FILES
# ==============================================================================

RANKINGS_PATH = os.path.join(
    HERE,
    "forecast_rankings.csv"
)

FORECAST_EVAL_PATH = os.path.join(
    HERE,
    "forecast_eval.csv"
)

CV_EVAL_PATH = os.path.join(
    HERE,
    "cv_eval.csv"
)


# ==============================================================================
# COMPLETE FORECAST LIGHT / DARK THEME
# ==============================================================================

_FORECAST_STYLE = """

<style>

/* =========================================================
   FORECAST THEME VARIABLES
   ========================================================= */

:root {

    color-scheme: light;

    --page-bg: #ffffff;
    --card-bg: #ffffff;
    --card-soft: #fafafa;

    --text-main: #111827;
    --text-secondary: #4b5563;
    --text-muted: #6b7280;

    --border: #e2e2e2;
    --border-soft: #eeeeee;

    --input-bg: #ffffff;
    --input-border: #cccccc;

    --blue: #2952a3;
    --blue-hover: #1d4ed8;

    --table-head: #f5f5f5;
    --table-hover: #f7f9ff;

    --success: #16803a;
    --danger: #c0392b;

    --shadow: rgba(0,0,0,.08);
}


/* =========================================================
   DARK MODE
   ========================================================= */

html.dark {

    color-scheme: dark;

    --page-bg: #0b0d11;
    --card-bg: #11151b;
    --card-soft: #151a21;

    --text-main: #f8fafc;
    --text-secondary: #d1d5db;
    --text-muted: #a1a1aa;

    --border: #303640;
    --border-soft: #272d36;

    --input-bg: #151a21;
    --input-border: #414957;

    --blue: #2563eb;
    --blue-hover: #3b82f6;

    --table-head: #171c23;
    --table-hover: #191f28;

    --success: #4ade80;
    --danger: #f87171;

    --shadow: rgba(0,0,0,.45);
}


/* =========================================================
   GLOBAL
   ========================================================= */

html {

    min-height:100%;

    background:
        var(--page-bg);

    transition:
        background-color .25s ease,
        color .25s ease;
}


body {

    font-family:
        -apple-system,
        BlinkMacSystemFont,
        "Segoe UI",
        Roboto,
        Arial,
        sans-serif;

    background:
        var(--page-bg);

    color:
        var(--text-main);

    margin:0;

    padding:24px;

    min-height:100vh;

    box-sizing:border-box;

    transition:
        background-color .25s ease,
        color .25s ease;
}


/* =========================================================
   MAIN CONTAINER
   ========================================================= */

body > * {

    box-sizing:border-box;
}


/* =========================================================
   HEADINGS
   ========================================================= */

h1,
h2,
h3,
h4,
h5,
h6 {

    color:
        var(--text-main);

    transition:
        color .25s ease;
}


h1 {

    font-size:20px;

    margin-top:0;

    margin-bottom:4px;
}


/* =========================================================
   SUBTEXT
   ========================================================= */

.sub {

    color:
        var(--text-muted);

    margin-bottom:20px;

    font-size:13px;

    line-height:1.55;
}


code {

    color:
        var(--text-main);

    background:
        var(--card-soft);

    padding:
        3px 6px;

    border-radius:4px;
}


/* =========================================================
   NAVIGATION
   ========================================================= */

.nav {

    margin-bottom:18px;

    display:flex;

    align-items:center;

    flex-wrap:wrap;

    gap:8px 18px;
}


.nav a {

    color:
        var(--blue);

    text-decoration:none;

    font-weight:600;

    font-size:13px;

    transition:
        color .2s ease;
}


.nav a:hover {

    color:
        var(--blue-hover);

    text-decoration:underline;
}


/* =========================================================
   THEME TOGGLE
   ========================================================= */

.forecast-topbar {

    display:flex;

    justify-content:flex-end;

    align-items:center;

    margin-bottom:12px;
}


.forecast-theme-toggle {

    display:inline-flex;

    align-items:center;

    justify-content:center;

    gap:7px;

    min-width:105px;

    padding:9px 15px;

    border-radius:999px;

    border:1px solid var(--border);

    background:var(--card-bg);

    color:var(--text-main);

    font-size:13px;

    font-weight:600;

    cursor:pointer;

    box-shadow:
        0 3px 12px var(--shadow);

    transition:
        background-color .2s ease,
        color .2s ease,
        border-color .2s ease,
        transform .15s ease,
        box-shadow .2s ease;
}


.forecast-theme-toggle:hover {

    background:
        var(--card-soft);

    transform:
        translateY(-1px);
}


.forecast-theme-toggle:active {

    transform:
        translateY(0);
}


/* =========================================================
   FILTER FORM
   ========================================================= */

form {

    background:
        var(--card-bg);

    border:
        1px solid var(--border);

    border-radius:
        10px;

    padding:
        14px 18px;

    margin-bottom:
        18px;

    display:
        flex;

    gap:
        14px;

    flex-wrap:
        wrap;

    align-items:
        flex-end;

    box-shadow:
        0 3px 12px var(--shadow);

    transition:
        background-color .25s ease,
        border-color .25s ease,
        box-shadow .25s ease;
}


/* =========================================================
   LABELS
   ========================================================= */

label {

    display:block;

    font-size:11px;

    color:
        var(--text-muted);

    text-transform:
        uppercase;

    margin-bottom:4px;

    font-weight:600;

    letter-spacing:.03em;
}


/* =========================================================
   INPUTS
   ========================================================= */

select,
input[type=text] {

    padding:
        8px 10px;

    border:
        1px solid var(--input-border);

    border-radius:
        6px;

    font-size:
        13px;

    min-width:
        140px;

    background:
        var(--input-bg);

    color:
        var(--text-main);

    outline:none;

    box-sizing:border-box;

    transition:
        background-color .25s ease,
        color .25s ease,
        border-color .25s ease,
        box-shadow .2s ease;
}


select:focus,
input[type=text]:focus {

    border-color:
        #3b82f6;

    box-shadow:
        0 0 0 2px rgba(59,130,246,.20);
}


input[type=text]::placeholder {

    color:
        var(--text-muted);
}


/* =========================================================
   SELECT OPTIONS
   ========================================================= */

html.dark select option {

    background:
        #151a21;

    color:
        #f8fafc;
}


/* =========================================================
   BUTTON
   ========================================================= */

button {

    background:
        var(--blue);

    color:
        #ffffff;

    border:none;

    padding:
        8px 16px;

    border-radius:
        6px;

    font-size:
        13px;

    font-weight:
        600;

    cursor:pointer;

    transition:
        background-color .2s ease,
        transform .15s ease,
        box-shadow .2s ease;
}


button:hover {

    background:
        var(--blue-hover);

    transform:
        translateY(-1px);

    box-shadow:
        0 4px 12px rgba(37,99,235,.25);
}


button:active {

    transform:
        translateY(0);
}


/* =========================================================
   TABLE
   ========================================================= */

table {

    border-collapse:
        separate;

    border-spacing:
        0;

    width:
        100%;

    background:
        var(--card-bg);

    color:
        var(--text-main);

    border:
        1px solid var(--border);

    border-radius:
        10px;

    overflow:
        hidden;

    box-shadow:
        0 3px 14px var(--shadow);

    transition:
        background-color .25s ease,
        border-color .25s ease,
        box-shadow .25s ease;
}


/* =========================================================
   TABLE CELLS
   ========================================================= */

th,
td {

    padding:
        9px 10px;

    text-align:
        left;

    border-bottom:
        1px solid var(--border-soft);

    font-size:
        13px;

    color:
        var(--text-main);

    transition:
        background-color .2s ease,
        color .2s ease,
        border-color .2s ease;
}


/* =========================================================
   TABLE HEADER
   ========================================================= */

th {

    background:
        var(--table-head);

    color:
        var(--text-secondary);

    font-weight:
        600;

    white-space:
        nowrap;
}


/* =========================================================
   TABLE HOVER
   ========================================================= */

tr:hover td {

    background:
        var(--table-hover);
}


/* =========================================================
   LAST ROW
   ========================================================= */

tr:last-child td {

    border-bottom:
        none;
}


/* =========================================================
   RANK
   ========================================================= */

.rank {

    font-weight:
        700;

    color:
        var(--blue);
}


/* =========================================================
   CHANGE COLORS
   ========================================================= */

.up {

    color:
        var(--success);

    font-weight:
        600;
}


.down {

    color:
        var(--danger);

    font-weight:
        600;
}


/* =========================================================
   EMPTY STATE
   ========================================================= */

.empty {

    padding:
        40px;

    text-align:
        center;

    color:
        var(--text-muted);

    background:
        var(--card-bg);

    border-radius:
        10px;

    border:
        1px solid var(--border);

    box-shadow:
        0 3px 14px var(--shadow);
}


/* =========================================================
   DATA TABLES GENERATED BY PANDAS
   ========================================================= */

.dataframe {

    width:
        100%;
}


/* =========================================================
   RESPONSIVE TABLE
   ========================================================= */

@media (max-width: 1100px) {

    body {

        padding:
            18px;
    }

    table {

        display:
            block;

        overflow-x:
            auto;

        white-space:
            nowrap;
    }
}


/* =========================================================
   MOBILE
   ========================================================= */

@media (max-width: 700px) {

    body {

        padding:
            12px;
    }


    .forecast-topbar {

        justify-content:
            flex-end;
    }


    .forecast-theme-toggle {

        min-width:
            100px;
    }


    form {

        flex-direction:
            column;

        align-items:
            stretch;
    }


    form > div {

        width:
            100%;
    }


    select,
    input[type=text] {

        width:
            100%;

        min-width:
            0;
    }


    form button {

        width:
            100%;
    }


    .nav {

        gap:
            10px 14px;
    }
}


/* =========================================================
   SCROLLBAR
   ========================================================= */

html.dark ::-webkit-scrollbar {

    width:
        10px;

    height:
        10px;
}


html.dark ::-webkit-scrollbar-track {

    background:
        #0b0d11;
}


html.dark ::-webkit-scrollbar-thumb {

    background:
        #343b46;

    border-radius:
        10px;
}


html.dark ::-webkit-scrollbar-thumb:hover {

    background:
        #4b5563;
}


/* =========================================================
   SMOOTH TRANSITIONS
   ========================================================= */

body,
table,
th,
td,
form,
select,
input,
button,
.empty,
.sub,
.nav a {

    transition:
        background-color .25s ease,
        color .25s ease,
        border-color .25s ease,
        box-shadow .25s ease;
}

</style>
"""


# ==============================================================================
# FORECAST THEME JAVASCRIPT
# ==============================================================================

_FORECAST_THEME_SCRIPT = """

<script>

(function () {

    const savedTheme =
        localStorage.getItem("ds-theme");

    let theme;

    if (
        savedTheme === "dark" ||
        savedTheme === "light"
    ) {

        theme = savedTheme;

    } else {

        theme =
            window.matchMedia &&
            window.matchMedia(
                "(prefers-color-scheme: dark)"
            ).matches
                ? "dark"
                : "light";
    }

    if (theme === "dark") {

        document.documentElement.classList.add(
            "dark"
        );

    } else {

        document.documentElement.classList.remove(
            "dark"
        );
    }

    document.documentElement.dataset.theme =
        theme;


    function updateButton() {

        const button =
            document.getElementById(
                "forecastThemeToggle"
            );

        if (!button) return;

        const isDark =
            document.documentElement.classList.contains(
                "dark"
            );

        if (isDark) {

            button.textContent =
                "☀️ Light";

            button.setAttribute(
                "aria-label",
                "Switch to light mode"
            );

            button.setAttribute(
                "title",
                "Switch to light mode"
            );

        } else {

            button.textContent =
                "🌙 Dark";

            button.setAttribute(
                "aria-label",
                "Switch to dark mode"
            );

            button.setAttribute(
                "title",
                "Switch to dark mode"
            );
        }
    }


    window.toggleForecastTheme =
        function () {

            const isDark =
                document.documentElement.classList.toggle(
                    "dark"
                );

            const newTheme =
                isDark
                    ? "dark"
                    : "light";

            localStorage.setItem(
                "ds-theme",
                newTheme
            );

            document.documentElement.dataset.theme =
                newTheme;

            updateButton();
        };


    document.addEventListener(
        "DOMContentLoaded",
        function () {

            updateButton();

        }
    );

})();

</script>
"""


# ==============================================================================
# FORECAST NAVIGATION
# ==============================================================================

_FORECAST_NAV = """

<div class="nav">

    <a href="/forecast">
        Rankings
    </a>

    <a href="/forecast/eval">
        Model Evaluation
    </a>

    <a href="/forecast/cv">
        Cross-Validation
    </a>

    <a href="/">
        &larr; Back to Data Scout
    </a>

</div>

"""


# ==============================================================================
# FORECAST PAGE HEADER
# ==============================================================================

def _forecast_header(
    title="Skill Ranking Forecast"
):

    return f"""

<div class="forecast-topbar">

    <button
        id="forecastThemeToggle"
        class="forecast-theme-toggle"
        type="button"
        onclick="toggleForecastTheme()"
    >
        🌙 Dark
    </button>

</div>

<h1>
    {title}
</h1>

"""


# ==============================================================================
# MISSING FORECAST FILE PAGE
# ==============================================================================

def _forecast_missing_page(
    title,
    filename,
    how_to_produce
):

    return HTMLResponse(
        f"""
<html>

<head>

<title>
    {title}
</title>

{_FORECAST_STYLE}

</head>

<body>

{_forecast_header(title)}

{_FORECAST_NAV}

<div class="empty">

    {filename} not found yet.

    <br>
    <br>

    Run:

    <br>

    <code>
        {how_to_produce}
    </code>

</div>

{_FORECAST_THEME_SCRIPT}

</body>

</html>
"""
    )


# ==============================================================================
# FORECAST JSON API
# ==============================================================================

@app.get("/api/forecast/rankings")
def api_forecast_rankings(

    league: str = Query(""),

    position: str = Query(""),

    search: str = Query(""),

    sort: str = Query(""),

    limit: int = Query(200)

):

    if not os.path.exists(
        RANKINGS_PATH
    ):

        return {
            "error":
            "forecast_rankings.csv not found — "
            "run: python ml_forecast.py"
        }


    df = pd.read_csv(
        RANKINGS_PATH
    )


    leagues = sorted(
        df["league"]
        .dropna()
        .unique()
        .tolist()
    )


    positions = sorted(
        df["primary_position"]
        .dropna()
        .unique()
        .tolist()
    )


    view = df


    if league:

        view = view[
            view["league"] == league
        ]


    if position:

        view = view[
            view["primary_position"] == position
        ]


    if search:

        view = view[
            view["player"]
            .str.contains(
                search,
                case=False,
                na=False
            )
        ]


    single_pool = (
        bool(league)
        and
        bool(position)
    )


    effective_sort = (
        sort
        or
        (
            "forecast_rank_in_pool"
            if single_pool
            else
            "forecast_next_composite"
        )
    )


    if effective_sort in view.columns:

        ascending = effective_sort in (
            "forecast_rank_in_pool",
            "player",
            "team"
        )

        view = view.sort_values(
            effective_sort,
            ascending=ascending
        )


    total_matches = len(view)

    view = view.head(limit)


    rows = []


    for i, (_, r) in enumerate(
        view.iterrows(),
        1
    ):

        delta = float(
            r["forecast_next_composite"]
            -
            r["composite_index"]
        )


        rows.append({

            "row_number": i,

            "pool_rank":
                int(
                    r["forecast_rank_in_pool"]
                ),

            "player":
                r["player"],

            "team":
                r["team"],

            "league":
                r["league"],

            "position":
                r["primary_position"],

            "age":
                float(
                    r["age_num"]
                ),

            "current_rating":
                float(
                    r["composite_index"]
                ),

            "forecast_rating":
                float(
                    r["forecast_next_composite"]
                ),

            "change":
                delta
        })


    return {

        "rows":
            rows,

        "total_matches":
            total_matches,

        "total_players":
            len(df),

        "leagues":
            leagues,

        "positions":
            positions
    }


# ==============================================================================
# EVALUATION API
# ==============================================================================

@app.get("/api/forecast/eval")
def api_forecast_eval():

    if not os.path.exists(
        FORECAST_EVAL_PATH
    ):

        return {
            "error":
            "forecast_eval.csv not found — "
            "run: python ml_forecast.py"
        }


    df = pd.read_csv(
        FORECAST_EVAL_PATH
    )


    return {
        "rows":
            df.to_dict(
                orient="records"
            )
    }


# ==============================================================================
# CROSS VALIDATION API
# ==============================================================================

@app.get("/api/forecast/cv")
def api_forecast_cv():

    if not os.path.exists(
        CV_EVAL_PATH
    ):

        return {
            "error":
            "cv_eval.csv not found — "
            "run: python ml_forecast.py --cv "
            "(or --fast-cv)"
        }


    df = pd.read_csv(
        CV_EVAL_PATH
    )


    summary = (
        df.groupby("model")
        [["mae", "spearman"]]
        .mean()
        .round(3)
        .sort_values(
            "spearman",
            ascending=False
        )
        .reset_index()
    )


    return {

        "rows":
            df.to_dict(
                orient="records"
            ),

        "summary":
            summary.to_dict(
                orient="records"
            )
    }


# ==============================================================================
# FORECAST RANKINGS PAGE
# ==============================================================================

@app.get(
    "/forecast",
    response_class=HTMLResponse
)
def forecast_rankings(

    league: str = Query(""),

    position: str = Query(""),

    search: str = Query(""),

    sort: str = Query(""),

    limit: int = Query(100)

):

    if not os.path.exists(
        RANKINGS_PATH
    ):

        return _forecast_missing_page(
            "Skill Ranking Forecast",
            "forecast_rankings.csv",
            "python ml_forecast.py"
        )


    df = pd.read_csv(
        RANKINGS_PATH
    )


    leagues = sorted(
        df["league"]
        .dropna()
        .unique()
    )


    positions = sorted(
        df["primary_position"]
        .dropna()
        .unique()
    )


    view = df


    if league:

        view = view[
            view["league"] == league
        ]


    if position:

        view = view[
            view["primary_position"] == position
        ]


    if search:

        view = view[
            view["player"]
            .str.contains(
                search,
                case=False,
                na=False
            )
        ]


    single_pool = (
        bool(league)
        and
        bool(position)
    )


    effective_sort = (
        sort
        or
        (
            "forecast_rank_in_pool"
            if single_pool
            else
            "forecast_next_composite"
        )
    )


    if effective_sort in view.columns:

        ascending = effective_sort in (
            "forecast_rank_in_pool",
            "player",
            "team"
        )

        view = view.sort_values(
            effective_sort,
            ascending=ascending
        )


    view = view.head(limit)


    def opt(
        value,
        current
    ):

        sel = (
            " selected"
            if str(value) == str(current)
            else ""
        )

        return (
            f'<option value="{value}"'
            f'{sel}>{value}</option>'
        )


    league_opts = (
        '<option value="">All leagues</option>'
        +
        "".join(
            opt(
                l,
                league
            )
            for l in leagues
        )
    )


    pos_opts = (
        '<option value="">All positions</option>'
        +
        "".join(
            opt(
                p,
                position
            )
            for p in positions
        )
    )


    pool_note = (

        '<div class="sub">'
        '"Pool rank" = rank within that player\'s '
        'own league+position group. '
        'Select both a League and a Position above '
        "to browse one pool's ranking; otherwise rows "
        "are sorted by forecasted score across everything shown."
        '</div>'

        '<div class="sub">'
        '<b>Current Rating</b> = composite skill score '
        'for their most recent season on record (0-100). '

        '<b>Forecasted Rating</b> = model\'s prediction '
        'for next season. '

        '<b>Change</b> = Forecasted &minus; Current: '

        '<span class="up">&#9650; green</span> '
        '= predicted to improve, '

        '<span class="down">&#9660; red</span> '
        '= predicted to decline.'
        '</div>'
    )


    rows_html = []


    for i, (_, r) in enumerate(
        view.iterrows(),
        1
    ):

        delta = (
            r["forecast_next_composite"]
            -
            r["composite_index"]
        )


        delta_cls = (
            "up"
            if delta >= 0
            else
            "down"
        )


        arrow = (
            "&#9650;"
            if delta >= 0
            else
            "&#9660;"
        )


        rows_html.append(
            f"""
<tr>

    <td class="rank">
        {i}
    </td>

    <td>
        {int(r['forecast_rank_in_pool'])}
    </td>

    <td>
        {r['player']}
    </td>

    <td>
        {r['team']}
    </td>

    <td>
        {r['league']}
    </td>

    <td>
        {r['primary_position']}
    </td>

    <td>
        {r['age_num']:.0f}
    </td>

    <td>
        {r['composite_index']:.1f}
    </td>

    <td>
        <b>
            {r['forecast_next_composite']:.1f}
        </b>
    </td>

    <td class="{delta_cls}">
        {arrow} {delta:+.1f}
    </td>

</tr>
"""
        )


    html = f"""

<html>

<head>

<title>
    Skill Ranking Forecast
</title>

{_FORECAST_STYLE}

</head>


<body>


{_forecast_header(
    "Next-Season Skill Ranking Forecast"
)}


<div class="sub">

    {len(view):,}
    of
    {len(df):,}
    player-pool rows shown

</div>


{pool_note}


{_FORECAST_NAV}


<form method="get">


    <div>

        <label>
            League
        </label>

        <select name="league">

            {league_opts}

        </select>

    </div>


    <div>

        <label>
            Position
        </label>

        <select name="position">

            {pos_opts}

        </select>

    </div>


    <div>

        <label>
            Search player
        </label>

        <input
            type="text"
            name="search"
            value="{search}"
            placeholder="Search player..."
        >

    </div>


    <div>

        <label>
            Rows
        </label>

        <select name="limit">

            {
                ''.join(
                    opt(
                        n,
                        str(limit)
                    )
                    for n in [
                        50,
                        100,
                        200,
                        500
                    ]
                )
            }

        </select>

    </div>


    <button
        type="submit"
    >
        Filter
    </button>


</form>


<table>

<tr>

    <th>
        #
    </th>

    <th>
        Pool Rank
    </th>

    <th>
        Player
    </th>

    <th>
        Team
    </th>

    <th>
        League
    </th>

    <th>
        Pos
    </th>

    <th>
        Age
    </th>

    <th>
        Current Rating
    </th>

    <th>
        Forecasted Rating (Next Season)
    </th>

    <th>
        Change
    </th>

</tr>


{
    ''.join(rows_html)
    if rows_html
    else
    '<tr><td colspan="10">No matches.</td></tr>'
}


</table>


{_FORECAST_THEME_SCRIPT}


</body>

</html>

"""


    return HTMLResponse(
        html
    )


# ==============================================================================
# MODEL EVALUATION PAGE
# ==============================================================================

@app.get(
    "/forecast/eval",
    response_class=HTMLResponse
)
def forecast_eval_page():

    if not os.path.exists(
        FORECAST_EVAL_PATH
    ):

        return _forecast_missing_page(
            "Model Evaluation",
            "forecast_eval.csv",
            "python ml_forecast.py"
        )


    df = pd.read_csv(
        FORECAST_EVAL_PATH
    )


    table = df.to_html(
        index=False,
        classes="dataframe",
        border=0
    )


    html = f"""

<html>

<head>

<title>
    Model Evaluation
</title>

{_FORECAST_STYLE}

</head>

<body>


{_forecast_header(
    "Model vs. Baseline Evaluation"
)}


<div class="sub">
    Held-out test set (time-based split)
</div>


{_FORECAST_NAV}


{table}


{_FORECAST_THEME_SCRIPT}


</body>

</html>

"""


    return HTMLResponse(
        html
    )


# ==============================================================================
# CROSS VALIDATION PAGE
# ==============================================================================

@app.get(
    "/forecast/cv",
    response_class=HTMLResponse
)
def forecast_cv_page():

    if not os.path.exists(
        CV_EVAL_PATH
    ):

        return _forecast_missing_page(
            "Cross-Validation",
            "cv_eval.csv",
            "python ml_forecast.py --cv (or --fast-cv)"
        )


    df = pd.read_csv(
        CV_EVAL_PATH
    )


    table = df.to_html(
        index=False,
        classes="dataframe",
        border=0
    )


    summary = (
        df.groupby("model")
        [["mae", "spearman"]]
        .mean()
        .round(3)
        .sort_values(
            "spearman",
            ascending=False
        )
    )


    summary_table = summary.to_html(
        classes="dataframe",
        border=0
    )


    html = f"""

<html>

<head>

<title>
    Cross-Validation
</title>

{_FORECAST_STYLE}

</head>

<body>


{_forecast_header(
    "Walk-Forward Cross-Validation"
)}


<div class="sub">
    Per season-cutoff results,
    then average across all cutoffs
</div>


{_FORECAST_NAV}


<h3
    style="
        font-size:14px;
        color:var(--text-main);
    "
>

    Average across cutoffs

</h3>


{summary_table}


<h3
    style="
        font-size:14px;
        margin-top:20px;
        color:var(--text-main);
    "
>

    Per cutoff

</h3>


{table}


{_FORECAST_THEME_SCRIPT}


</body>

</html>

"""


    return HTMLResponse(
        html
    )


# ==============================================================================
# RUN SERVER
# ==============================================================================

if __name__ == "__main__":

    import uvicorn

    print(
        "\n"
        + "=" * 60
    )

    print(
        "  Data Scout is running."
    )

    print(
        "  -> Open http://localhost:8000"
    )

    print(
        "  -> Forecast http://localhost:8000/forecast"
    )

    print(
        "=" * 60
        + "\n"
    )

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000
    )