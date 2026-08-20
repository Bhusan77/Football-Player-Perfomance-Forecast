import { useEffect, useState } from "react";

/* =========================================================
   API HELPERS
   ========================================================= */

function buildQuery(params) {
  const parts = Object.entries(params)
    .filter(([, value]) => value !== undefined && value !== "")
    .map(
      ([key, value]) =>
        `${encodeURIComponent(key)}=${encodeURIComponent(value)}`
    );

  return parts.length ? `?${parts.join("&")}` : "";
}

async function fetchRankings(filters) {
  const response = await fetch(
    `/api/forecast/rankings${buildQuery(filters)}`
  );

  if (!response.ok) {
    throw new Error("Failed to load ranking data.");
  }

  return response.json();
}

async function fetchEval() {
  const response = await fetch("/api/forecast/eval");

  if (!response.ok) {
    throw new Error("Failed to load evaluation data.");
  }

  return response.json();
}

async function fetchCv() {
  const response = await fetch("/api/forecast/cv");

  if (!response.ok) {
    throw new Error("Failed to load cross-validation data.");
  }

  return response.json();
}

/* =========================================================
   THEME
   ========================================================= */

function getInitialTheme() {
  const storedTheme = localStorage.getItem("theme");

  if (storedTheme === "light" || storedTheme === "dark") {
    return storedTheme;
  }

  return window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
}

function useTheme() {
  const [theme, setTheme] = useState(getInitialTheme);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);

    document.documentElement.classList.toggle(
      "dark",
      theme === "dark"
    );

    localStorage.setItem("theme", theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme((currentTheme) =>
      currentTheme === "dark" ? "light" : "dark"
    );
  };

  return [theme, toggleTheme];
}

/* =========================================================
   THEME TOGGLE
   ========================================================= */

function ThemeToggle({ theme, onToggle }) {
  return (
    <button
      className="theme-toggle"
      onClick={onToggle}
      type="button"
      aria-label={`Switch to ${
        theme === "dark" ? "light" : "dark"
      } mode`}
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

/* =========================================================
   LOADING COMPONENT
   ========================================================= */

function LoadingState({ text = "Loading..." }) {
  return (
    <div className="empty">
      <div className="spinner" />
      <span>{text}</span>
    </div>
  );
}

/* =========================================================
   ERROR COMPONENT
   ========================================================= */

function ErrorState({ message }) {
  return (
    <div className="empty error-state">
      <div className="error-icon">!</div>

      <strong>Something went wrong</strong>

      <span>{message}</span>
    </div>
  );
}

/* =========================================================
   RANKINGS VIEW
   ========================================================= */

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
      .finally(() => {
        setLoading(false);
      });
  }, [league, position, search, limit]);

  if (loading && !data) {
    return <LoadingState text="Loading forecasts..." />;
  }

  if (data?.error) {
    return <ErrorState message={data.error} />;
  }

  if (!data) {
    return null;
  }

  return (
    <div className="forecast-section">

      {/* =====================================================
          PAGE INTRO
          ===================================================== */}

      <div className="dashboard-heading">

        <div>
          <span className="eyebrow">
            MACHINE LEARNING ANALYTICS
          </span>

          <h2>Player Skill Rankings</h2>

          <p>
            Forecasted player skill ratings generated from
            historical football match data.
          </p>
        </div>

        <div className="dataset-status">
          <span className="status-dot" />
          Forecast dataset loaded
        </div>

      </div>

      {/* =====================================================
          SUMMARY CARDS
          ===================================================== */}

      <div className="summary-grid">

        <div className="summary-card">

          <div className="summary-icon blue">
            ⚽
          </div>

          <div>
            <span className="summary-label">
              Matching Rows
            </span>

            <strong>
              {data.total_matches.toLocaleString()}
            </strong>

            <small>
              Player-pool records
            </small>
          </div>

        </div>

        <div className="summary-card">

          <div className="summary-icon purple">
            👥
          </div>

          <div>
            <span className="summary-label">
              Player Pool
            </span>

            <strong>
              {data.total_players.toLocaleString()}
            </strong>

            <small>
              Players available
            </small>
          </div>

        </div>

        <div className="summary-card">

          <div className="summary-icon green">
            📈
          </div>

          <div>
            <span className="summary-label">
              Forecast Type
            </span>

            <strong>
              Next Season
            </strong>

            <small>
              ML-based prediction
            </small>
          </div>

        </div>

      </div>

      {/* =====================================================
          INFORMATION PANEL
          ===================================================== */}

      <div className="info-card">

        <div className="info-line">

          <span className="info-icon">
            ℹ
          </span>

          <span>
            <b>Pool Rank</b> represents a player's
            rank within their own league and position
            group. Select both League and Position
            to browse a specific ranking pool.
          </span>

        </div>

        <div className="info-line">

          <span className="info-icon">
            🎯
          </span>

          <span>
            <b>Current Rating</b> is the most recent
            recorded composite skill score.
            <b> Forecasted Rating</b> represents the
            machine learning prediction for the next
            season.
          </span>

        </div>

        <div className="info-line">

          <span className="info-icon">
            ↕
          </span>

          <span>
            <b>Change</b> is calculated as Forecasted
            Rating − Current Rating.
            <span className="up"> ▲ Improvement</span>
            and
            <span className="down"> ▼ Decline</span>.
          </span>

        </div>

      </div>

      {/* =====================================================
          FILTERS
          ===================================================== */}

      <form
        className="filters"
        onSubmit={(event) => event.preventDefault()}
      >

        <div className="filter-title">
          <span className="filter-title-icon">
            ⚙
          </span>

          <div>
            <strong>Ranking Filters</strong>

            <small>
              Refine the player ranking results
            </small>
          </div>
        </div>

        <div className="filter-group">

          <label htmlFor="league">
            League
          </label>

          <select
            id="league"
            value={league}
            onChange={(event) =>
              setLeague(event.target.value)
            }
          >
            <option value="">
              All leagues
            </option>

            {data.leagues.map((item) => (
              <option
                key={item}
                value={item}
              >
                {item}
              </option>
            ))}
          </select>

        </div>

        <div className="filter-group">

          <label htmlFor="position">
            Position
          </label>

          <select
            id="position"
            value={position}
            onChange={(event) =>
              setPosition(event.target.value)
            }
          >
            <option value="">
              All positions
            </option>

            {data.positions.map((item) => (
              <option
                key={item}
                value={item}
              >
                {item}
              </option>
            ))}
          </select>

        </div>

        <div className="filter-group search-group">

          <label htmlFor="player-search">
            Search Player
          </label>

          <div className="search-input-wrapper">

            <span className="search-icon">
              🔍
            </span>

            <input
              id="player-search"
              type="text"
              value={search}
              onChange={(event) =>
                setSearch(event.target.value)
              }
              placeholder="e.g. Haaland"
            />

          </div>

        </div>

        <div className="filter-group">

          <label htmlFor="rows">
            Rows
          </label>

          <select
            id="rows"
            value={limit}
            onChange={(event) =>
              setLimit(Number(event.target.value))
            }
          >
            {[50, 100, 200, 500].map((number) => (
              <option
                key={number}
                value={number}
              >
                {number}
              </option>
            ))}
          </select>

        </div>

        {loading && (
          <div className="loading-tag">

            <span className="mini-spinner" />

            Updating...

          </div>
        )}

      </form>

      {/* =====================================================
          TABLE
          ===================================================== */}

      <div className="table-card">

        <div className="table-header">

          <div>

            <h3>
              Forecast Rankings
            </h3>

            <p>
              Player skill ranking based on model
              predictions.
            </p>

          </div>

          <div className="table-count">

            {data.rows.length} results

          </div>

        </div>

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

                  <td
                    colSpan={10}
                    className="no-results"
                  >
                    No matching players found.
                  </td>

                </tr>

              )}

              {data.rows.map((row) => (

                <tr
                  key={`${row.player}-${row.team}-${row.league}`}
                >

                  <td className="rank">
                    {row.row_number}
                  </td>

                  <td>

                    <span className="pool-rank">
                      #{row.pool_rank}
                    </span>

                  </td>

                  <td>

                    <strong className="player-name">
                      {row.player}
                    </strong>

                  </td>

                  <td>
                    {row.team}
                  </td>

                  <td>
                    {row.league}
                  </td>

                  <td>

                    <span className="position-badge">
                      {row.position}
                    </span>

                  </td>

                  <td>
                    {Number(row.age).toFixed(0)}
                  </td>

                  <td>

                    <span className="current-rating">
                      {Number(
                        row.current_rating
                      ).toFixed(1)}
                    </span>

                  </td>

                  <td>

                    <strong className="forecast-rating">
                      {Number(
                        row.forecast_rating
                      ).toFixed(1)}
                    </strong>

                  </td>

                  <td
                    className={
                      row.change >= 0
                        ? "change-cell up"
                        : "change-cell down"
                    }
                  >

                    <span className="change-badge">

                      {row.change >= 0
                        ? "▲"
                        : "▼"}

                      {" "}

                      {row.change >= 0
                        ? "+"
                        : ""}

                      {Number(
                        row.change
                      ).toFixed(1)}

                    </span>

                  </td>

                </tr>

              ))}

            </tbody>

          </table>

        </div>

      </div>

    </div>
  );
}

/* =========================================================
   MODEL EVALUATION VIEW
   ========================================================= */

function EvalView() {

  const [data, setData] = useState(null);

  useEffect(() => {

    fetchEval()
      .then(setData)
      .catch(() => {

        setData({
          error:
            "Unable to load model evaluation data.",
        });

      });

  }, []);

  if (!data) {
    return <LoadingState />;
  }

  if (data.error) {
    return <ErrorState message={data.error} />;
  }

  return (

    <div className="forecast-section">

      {/* PAGE TITLE */}

      <div className="dashboard-heading">

        <div>

          <span className="eyebrow">
            MODEL PERFORMANCE
          </span>

          <h2>
            Model vs. Baseline Evaluation
          </h2>

          <p>
            Evaluation results using a held-out
            time-based test set.
          </p>

        </div>

        <div className="evaluation-badge">
          🧠 Machine Learning
        </div>

      </div>

      {/* METRICS */}

      <div className="metric-banner">

        <div className="metric-item">

          <span className="metric-icon">
            🧠
          </span>

          <div>

            <strong>
              Machine Learning Model
            </strong>

            <small>
              Forecast performance
            </small>

          </div>

        </div>

        <div className="metric-item">

          <span className="metric-icon">
            📉
          </span>

          <div>

            <strong>
              MAE
            </strong>

            <small>
              Mean Absolute Error
            </small>

          </div>

        </div>

        <div className="metric-item">

          <span className="metric-icon">
            🏆
          </span>

          <div>

            <strong>
              Spearman
            </strong>

            <small>
              Rank correlation
            </small>

          </div>

        </div>

      </div>

      {/* TABLE */}

      <div className="table-card">

        <div className="table-header">

          <div>

            <h3>
              Evaluation Results
            </h3>

            <p>
              Comparison of model performance
              across player positions.
            </p>

          </div>

        </div>

        <div className="table-wrapper">

          <table>

            <thead>

              <tr>

                <th>
                  Model
                </th>

                <th>
                  Position
                </th>

                <th>
                  N (Test Rows)
                </th>

                <th>
                  MAE
                </th>

                <th>
                  Spearman
                </th>

              </tr>

            </thead>

            <tbody>

              {data.rows.map((row, index) => (

                <tr key={index}>

                  <td>

                    <strong className="model-name">
                      {row.model}
                    </strong>

                  </td>

                  <td>

                    <span className="position-badge">
                      {row.position}
                    </span>

                  </td>

                  <td>
                    {row.n_test.toLocaleString()}
                  </td>

                  <td>

                    <span className="metric-value">
                      {row.mae}
                    </span>

                  </td>

                  <td>

                    <span className="metric-value">
                      {row.spearman}
                    </span>

                  </td>

                </tr>

              ))}

            </tbody>

          </table>

        </div>

      </div>

    </div>
  );
}

/* =========================================================
   CROSS VALIDATION VIEW
   ========================================================= */

function CvView() {

  const [data, setData] = useState(null);

  useEffect(() => {

    fetchCv()
      .then(setData)
      .catch(() => {

        setData({
          error:
            "Unable to load cross-validation data.",
        });

      });

  }, []);

  if (!data) {
    return <LoadingState />;
  }

  if (data.error) {
    return <ErrorState message={data.error} />;
  }

  return (

    <div className="forecast-section">

      {/* PAGE TITLE */}

      <div className="dashboard-heading">

        <div>

          <span className="eyebrow">
            MODEL VALIDATION
          </span>

          <h2>
            Walk-Forward Cross-Validation
          </h2>

          <p>
            Performance evaluated across multiple
            historical season cutoffs.
          </p>

        </div>

        <div className="evaluation-badge">
          🔄 Time-Series Validation
        </div>

      </div>

      {/* SECTION 01 */}

      <div className="section-heading">

        <div>

          <span className="section-number">
            01
          </span>

          <div>

            <h3>
              Average Across Cutoffs
            </h3>

            <p>
              Overall model performance across
              validation periods.
            </p>

          </div>

        </div>

      </div>

      <div className="table-card">

        <div className="table-wrapper">

          <table>

            <thead>

              <tr>

                <th>
                  Model
                </th>

                <th>
                  MAE
                </th>

                <th>
                  Spearman
                </th>

              </tr>

            </thead>

            <tbody>

              {data.summary.map((row, index) => (

                <tr key={index}>

                  <td>

                    <strong className="model-name">
                      {row.model}
                    </strong>

                  </td>

                  <td>

                    <span className="metric-value">
                      {row.mae}
                    </span>

                  </td>

                  <td>

                    <span className="metric-value">
                      {row.spearman}
                    </span>

                  </td>

                </tr>

              ))}

            </tbody>

          </table>

        </div>

      </div>

      {/* SECTION 02 */}

      <div className="section-heading second-heading">

        <div>

          <span className="section-number">
            02
          </span>

          <div>

            <h3>
              Per Cutoff
            </h3>

            <p>
              Individual validation results for
              each season cutoff.
            </p>

          </div>

        </div>

      </div>

      <div className="table-card">

        <div className="table-wrapper">

          <table>

            <thead>

              <tr>

                <th>
                  Cutoff Season
                </th>

                <th>
                  Model
                </th>

                <th>
                  N (Test Rows)
                </th>

                <th>
                  MAE
                </th>

                <th>
                  Spearman
                </th>

              </tr>

            </thead>

            <tbody>

              {data.rows.map((row, index) => (

                <tr key={index}>

                  <td>

                    <span className="season-badge">
                      {row.cutoff_season}
                    </span>

                  </td>

                  <td>

                    <strong className="model-name">
                      {row.model}
                    </strong>

                  </td>

                  <td>
                    {row.n_test.toLocaleString()}
                  </td>

                  <td>

                    <span className="metric-value">
                      {row.mae}
                    </span>

                  </td>

                  <td>

                    <span className="metric-value">
                      {row.spearman}
                    </span>

                  </td>

                </tr>

              ))}

            </tbody>

          </table>

        </div>

      </div>

    </div>
  );
}

/* =========================================================
   MAIN APPLICATION
   ========================================================= */

export default function App() {

  const [tab, setTab] = useState("rankings");

  const [theme, toggleTheme] = useTheme();

  return (

    <div className="app">

      {/* =====================================================
          HEADER
          ===================================================== */}

      <header className="app-header">

        <div className="brand-area">

          <div className="brand-icon">
            ⚽
          </div>

          <div>

            <span className="brand-label">
              FOOTBALL ANALYTICS
            </span>

            <h1>
              Skill Ranking Forecast
            </h1>

            <p className="subtitle">
              Machine learning based player skill
              ranking and next-season forecasting.
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

      {/* =====================================================
          NAVIGATION
          ===================================================== */}

      <nav className="tabs">

        <button
          type="button"
          className={
            tab === "rankings"
              ? "active"
              : ""
          }
          onClick={() =>
            setTab("rankings")
          }
        >

          <span>
            🏆
          </span>

          Rankings

        </button>

        <button
          type="button"
          className={
            tab === "eval"
              ? "active"
              : ""
          }
          onClick={() =>
            setTab("eval")
          }
        >

          <span>
            📊
          </span>

          Model Evaluation

        </button>

        <button
          type="button"
          className={
            tab === "cv"
              ? "active"
              : ""
          }
          onClick={() =>
            setTab("cv")
          }
        >

          <span>
            🔄
          </span>

          Cross-Validation

        </button>

      </nav>

      {/* =====================================================
          CONTENT
          ===================================================== */}

      <main>

        {tab === "rankings" && (
          <RankingsView />
        )}

        {tab === "eval" && (
          <EvalView />
        )}

        {tab === "cv" && (
          <CvView />
        )}

      </main>

      {/* =====================================================
          FOOTER
          ===================================================== */}

      <footer className="app-footer">

        <div>

          <strong>
            Skill Ranking Forecast
          </strong>

          <span>
            Machine Learning Analytics
          </span>

        </div>

        <div>
          Football Performance Forecasting
        </div>

      </footer>

    </div>
  );
}

/* =========================================================
   DATA SCOUT DARK MODE
   ========================================================= */

(function setupDataScoutTheme() {
  const STORAGE_KEY = "data-scout-theme";

  function getSavedTheme() {
    const saved = localStorage.getItem(STORAGE_KEY);

    if (saved === "dark" || saved === "light") {
      return saved;
    }

    return window.matchMedia &&
      window.matchMedia("(prefers-color-scheme: dark)").matches
      ? "dark"
      : "light";
  }

  function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);

    document.documentElement.classList.toggle(
      "dark",
      theme === "dark"
    );

    localStorage.setItem(STORAGE_KEY, theme);

    const button = document.getElementById(
      "data-scout-theme-toggle"
    );

    if (button) {
      const icon = button.querySelector(
        ".data-scout-theme-icon"
      );

      const text = button.querySelector(
        ".data-scout-theme-text"
      );

      if (theme === "dark") {
        if (icon) {
          icon.textContent = "☀";
        }

        if (text) {
          text.textContent = "Light Mode";
        }

        button.setAttribute(
          "aria-label",
          "Switch to light mode"
        );
      } else {
        if (icon) {
          icon.textContent = "☾";
        }

        if (text) {
          text.textContent = "Dark Mode";
        }

        button.setAttribute(
          "aria-label",
          "Switch to dark mode"
        );
      }
    }
  }

  function createThemeButton() {
    if (
      document.getElementById(
        "data-scout-theme-toggle"
      )
    ) {
      return;
    }

    const button = document.createElement("button");

    button.id = "data-scout-theme-toggle";

    button.className =
      "data-scout-theme-toggle";

    button.type = "button";

    button.innerHTML = `
      <span class="data-scout-theme-icon">☾</span>
      <span class="data-scout-theme-text">
        Dark Mode
      </span>
    `;

    button.addEventListener("click", function () {
      const currentTheme =
        document.documentElement.getAttribute(
          "data-theme"
        ) || "light";

      const newTheme =
        currentTheme === "dark"
          ? "light"
          : "dark";

      applyTheme(newTheme);
    });

    document.body.appendChild(button);

    applyTheme(getSavedTheme());
  }

  function initialiseTheme() {
    const theme = getSavedTheme();

    document.documentElement.setAttribute(
      "data-theme",
      theme
    );

    document.documentElement.classList.toggle(
      "dark",
      theme === "dark"
    );

    createThemeButton();
  }

  if (document.readyState === "loading") {
    document.addEventListener(
      "DOMContentLoaded",
      initialiseTheme
    );
  } else {
    initialiseTheme();
  }
})();