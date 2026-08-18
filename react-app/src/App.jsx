import { useEffect, useState } from "react";

function buildQuery(params) {
  const parts = Object.entries(params)
    .filter(([, v]) => v !== undefined && v !== "")
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`);

  return parts.length ? `?${parts.join("&")}` : "";
}

async function fetchRankings(filters) {
  const res = await fetch(`/api/forecast/rankings${buildQuery(filters)}`);
  return res.json();
}

async function fetchEval() {
  const res = await fetch("/api/forecast/eval");
  return res.json();
}

async function fetchCv() {
  const res = await fetch("/api/forecast/cv");
  return res.json();
}

function getInitialTheme() {
  const stored = localStorage.getItem("theme");

  if (stored === "light" || stored === "dark") {
    return stored;
  }

  return window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
}

function useTheme() {
  const [theme, setTheme] = useState(getInitialTheme);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);

    // Keep Tailwind-based components synchronized too
    document.documentElement.classList.toggle("dark", theme === "dark");

    localStorage.setItem("theme", theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme((currentTheme) =>
      currentTheme === "dark" ? "light" : "dark"
    );
  };

  return [theme, toggleTheme];
}

function ThemeToggle({ theme, onToggle }) {
  return (
    <button
      className="theme-toggle"
      onClick={onToggle}
      type="button"
      aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
    >
      <span className="theme-icon">
        {theme === "dark" ? "☀" : "☾"}
      </span>

      <span>
        {theme === "dark" ? "Light Mode" : "Dark Mode"}
      </span>
    </button>
  );
}


function RankingsView() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [league, setLeague] = useState("");
  const [position, setPosition] = useState("");
  const [search, setSearch] = useState("");
  const [limit, setLimit] = useState(50);

  useEffect(() => {
    setLoading(true);

    fetchRankings({
      league,
      position,
      search,
      limit,
    })
      .then(setData)
      .catch(() => {
        setData({
          error: "Unable to load ranking data.",
        });
      })
      .finally(() => setLoading(false));
  }, [league, position, search, limit]);

  if (loading && !data) {
    return (
      <div className="empty">
        <div className="spinner" />
        <span>Loading forecasts...</span>
      </div>
    );
  }

  if (data?.error) {
    return <div className="empty">{data.error}</div>;
  }

  if (!data) return null;

  return (
    <div className="forecast-section">
      <div className="info-card">
        <div className="info-line">
          <span className="info-icon">📊</span>
          <span>
            <strong>{data.total_matches.toLocaleString()}</strong> of{" "}
            <strong>{data.total_players.toLocaleString()}</strong> player-pool
            rows match
          </span>
        </div>

        <div className="info-line">
          <span className="info-icon">ℹ</span>
          <span>
            <b>Pool Rank</b> = rank within that player's own league + position
            group. Select both a League and a Position to browse one pool's
            ranking in order; otherwise rows are sorted by forecasted score
            across everything shown.
          </span>
        </div>

        <div className="info-line">
          <span className="info-icon">🎯</span>
          <span>
            <b>Current Rating</b> = composite skill score for their most recent
            season on record (0-100).{" "}
            <b>Forecasted Rating</b> = model's prediction for next season.{" "}
            <b>Change</b> = Forecasted − Current.
            <span className="up"> ▲ green</span> = predicted to improve,
            <span className="down"> ▼ red</span> = predicted to decline.
          </span>
        </div>
      </div>

      <form
        className="filters"
        onSubmit={(e) => e.preventDefault()}
      >
        <div className="filter-group">
          <label>League</label>

          <select
            value={league}
            onChange={(e) => setLeague(e.target.value)}
          >
            <option value="">All leagues</option>

            {data.leagues.map((l) => (
              <option key={l} value={l}>
                {l}
              </option>
            ))}
          </select>
        </div>

        <div className="filter-group">
          <label>Position</label>

          <select
            value={position}
            onChange={(e) => setPosition(e.target.value)}
          >
            <option value="">All positions</option>

            {data.positions.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </div>

        <div className="filter-group search-group">
          <label>Search Player</label>

          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="e.g. Haaland"
          />
        </div>

        <div className="filter-group">
          <label>Rows</label>

          <select
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
          >
            {[50, 100, 200, 500].map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </div>

        {loading && (
          <span className="loading-tag">
            <span className="mini-spinner" />
            Updating...
          </span>
        )}
      </form>

      <div className="table-wrapper">
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>Pool Rank</th>
              <th>Player</th>
              <th>Team</th>
              <th>League</th>
              <th>Pos</th>
              <th>Age</th>
              <th>Current Rating</th>
              <th>Forecasted Rating</th>
              <th>Change</th>
            </tr>
          </thead>

          <tbody>
            {data.rows.length === 0 && (
              <tr>
                <td colSpan={10} className="no-results">
                  No matches found.
                </td>
              </tr>
            )}

            {data.rows.map((r) => (
              <tr
                key={`${r.player}-${r.team}-${r.league}`}
              >
                <td className="rank">
                  {r.row_number}
                </td>

                <td>
                  <span className="pool-rank">
                    {r.pool_rank}
                  </span>
                </td>

                <td>
                  <strong className="player-name">
                    {r.player}
                  </strong>
                </td>

                <td>{r.team}</td>

                <td>{r.league}</td>

                <td>
                  <span className="position-badge">
                    {r.position}
                  </span>
                </td>

                <td>{r.age.toFixed(0)}</td>

                <td>
                  <span className="current-rating">
                    {r.current_rating.toFixed(1)}
                  </span>
                </td>

                <td>
                  <strong className="forecast-rating">
                    {r.forecast_rating.toFixed(1)}
                  </strong>
                </td>

                <td
                  className={
                    r.change >= 0
                      ? "change-cell up"
                      : "change-cell down"
                  }
                >
                  <span className="change-badge">
                    {r.change >= 0 ? "▲" : "▼"}{" "}
                    {r.change >= 0 ? "+" : ""}
                    {r.change.toFixed(1)}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Model Evaluation tab
// ---------------------------------------------------------------------------

function EvalView() {
  const [data, setData] = useState(null);

  useEffect(() => {
    fetchEval()
      .then(setData)
      .catch(() => {
        setData({
          error: "Unable to load model evaluation data.",
        });
      });
  }, []);

  if (!data) {
    return (
      <div className="empty">
        <div className="spinner" />
        <span>Loading...</span>
      </div>
    );
  }

  if (data.error) {
    return <div className="empty">{data.error}</div>;
  }

  return (
    <div className="forecast-section">
      <div className="page-title">
        <h2>Model vs. Baseline Evaluation</h2>
        <p>Held-out test set using a time-based split.</p>
      </div>

      <div className="metric-banner">
        <div className="metric-item">
          <span className="metric-icon">🧠</span>
          <div>
            <strong>Machine Learning Model</strong>
            <small>Forecast performance</small>
          </div>
        </div>

        <div className="metric-item">
          <span className="metric-icon">📈</span>
          <div>
            <strong>MAE</strong>
            <small>Mean Absolute Error</small>
          </div>
        </div>

        <div className="metric-item">
          <span className="metric-icon">🏆</span>
          <div>
            <strong>Spearman</strong>
            <small>Rank correlation</small>
          </div>
        </div>
      </div>

      <div className="table-wrapper">
        <table>
          <thead>
            <tr>
              <th>Model</th>
              <th>Position</th>
              <th>N (Test Rows)</th>
              <th>MAE</th>
              <th>Spearman</th>
            </tr>
          </thead>

          <tbody>
            {data.rows.map((r, i) => (
              <tr key={i}>
                <td>
                  <strong className="model-name">
                    {r.model}
                  </strong>
                </td>

                <td>
                  <span className="position-badge">
                    {r.position}
                  </span>
                </td>

                <td>
                  {r.n_test.toLocaleString()}
                </td>

                <td>
                  <span className="metric-value">
                    {r.mae}
                  </span>
                </td>

                <td>
                  <span className="metric-value">
                    {r.spearman}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Cross-Validation tab
// ---------------------------------------------------------------------------

function CvView() {
  const [data, setData] = useState(null);

  useEffect(() => {
    fetchCv()
      .then(setData)
      .catch(() => {
        setData({
          error: "Unable to load cross-validation data.",
        });
      });
  }, []);

  if (!data) {
    return (
      <div className="empty">
        <div className="spinner" />
        <span>Loading...</span>
      </div>
    );
  }

  if (data.error) {
    return <div className="empty">{data.error}</div>;
  }

  return (
    <div className="forecast-section">
      <div className="page-title">
        <h2>Walk-Forward Cross-Validation</h2>
        <p>
          Per season-cutoff results, followed by averages across all
          cutoffs.
        </p>
      </div>

      <div className="section-heading">
        <div>
          <span className="section-number">01</span>
          <div>
            <h3>Average Across Cutoffs</h3>
            <p>Overall model performance across validation periods.</p>
          </div>
        </div>
      </div>

      <div className="table-wrapper">
        <table>
          <thead>
            <tr>
              <th>Model</th>
              <th>MAE</th>
              <th>Spearman</th>
            </tr>
          </thead>

          <tbody>
            {data.summary.map((r, i) => (
              <tr key={i}>
                <td>
                  <strong className="model-name">
                    {r.model}
                  </strong>
                </td>

                <td>
                  <span className="metric-value">
                    {r.mae}
                  </span>
                </td>

                <td>
                  <span className="metric-value">
                    {r.spearman}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="section-heading second-heading">
        <div>
          <span className="section-number">02</span>
          <div>
            <h3>Per Cutoff</h3>
            <p>Individual validation results for each season cutoff.</p>
          </div>
        </div>
      </div>

      <div className="table-wrapper">
        <table>
          <thead>
            <tr>
              <th>Cutoff Season</th>
              <th>Model</th>
              <th>N (Test Rows)</th>
              <th>MAE</th>
              <th>Spearman</th>
            </tr>
          </thead>

          <tbody>
            {data.rows.map((r, i) => (
              <tr key={i}>
                <td>
                  <span className="season-badge">
                    {r.cutoff_season}
                  </span>
                </td>

                <td>
                  <strong className="model-name">
                    {r.model}
                  </strong>
                </td>

                <td>
                  {r.n_test.toLocaleString()}
                </td>

                <td>
                  <span className="metric-value">
                    {r.mae}
                  </span>
                </td>

                <td>
                  <span className="metric-value">
                    {r.spearman}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// App shell
// ---------------------------------------------------------------------------

export default function App() {
  const [tab, setTab] = useState("rankings");
  const [theme, toggleTheme] = useTheme();

  return (
    <div className="app">
      <header className="app-header">
        <div className="brand-area">
          <div className="brand-icon">
            ⚽
          </div>

          <div>
            <h1>Skill Ranking Forecast</h1>

            <p className="subtitle">
              ML-forecasted next-season player skill ranking, built on
              historical match data.
            </p>
          </div>
        </div>

        <div className="header-right">
          <ThemeToggle
            theme={theme}
            onToggle={toggleTheme}
          />

          <a
            className="back-link"
            href="http://localhost:8000/"
          >
            <span>←</span>
            Data Scout
          </a>
        </div>
      </header>

      <nav className="tabs">
        <button
          className={tab === "rankings" ? "active" : ""}
          onClick={() => setTab("rankings")}
        >
          <span>🏆</span>
          Rankings
        </button>

        <button
          className={tab === "eval" ? "active" : ""}
          onClick={() => setTab("eval")}
        >
          <span>📊</span>
          Model Evaluation
        </button>

        <button
          className={tab === "cv" ? "active" : ""}
          onClick={() => setTab("cv")}
        >
          <span>🔄</span>
          Cross-Validation
        </button>
      </nav>

      <main>
        {tab === "rankings" && <RankingsView />}

        {tab === "eval" && <EvalView />}

        {tab === "cv" && <CvView />}
      </main>

      <footer className="app-footer">
        <span>Skill Ranking Forecast</span>
        <span>•</span>
        <span>Machine Learning Analytics</span>
      </footer>
    </div>
  );
}