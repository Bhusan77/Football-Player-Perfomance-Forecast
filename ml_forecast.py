#!/usr/bin/env python3
"""
ml_forecast.py — Forecasting player skill ranking from historical match data.

Drop this file into the SAME folder as scout_engine.py / players.csv.gz /
supplementary.csv.gz (the footylytics-data-scout-lab-data folder). It reuses
the real course engine's own composite-index logic (scout_engine.py) as the
ground-truth "skill ranking" score, builds season-over-season lag features,
and trains an ML model to forecast a player's NEXT-season skill ranking from
their CURRENT/PAST season's historical match data.

Why composite_index and not power_rating:
    power_rating is mostly a league-strength constant (Premier League=100,
    Bundesliga=86.3, ...) baked into the data, not an individual skill score.
    scout_engine.calculate_composite_index() is the engine's real per-player
    performance rating: 40% z-scored per-90 stats + 30% style-percentile +
    30% power rating, computed within each season/league/position pool. It
    IS the skill ranking, so it's the correct forecasting target.

Compares two gradient-boosted tree models — scikit-learn's GradientBoosting
and XGBoost (if installed) — as the "appropriate ML techniques" for this
ranking task, and automatically deploys whichever scores higher on Spearman
rank correlation (the right metric for a ranking forecast, not raw MAE).

Usage:
    pip install -r requirements.txt
    pip install xgboost                    # optional, enables the model comparison
    python ml_forecast.py                  # build data, train, evaluate, save model
    python ml_forecast.py --season 2025-2026 --league premier-league --position FW
                                            # print forecast rankings for one pool

Outputs (written next to this script):
    composite_full.pkl   cached historical composite-index dataset (rebuild with --rebuild)
    forecast_model.pkl   trained GradientBoostingRegressor + feature list
    forecast_eval.csv    per-position evaluation vs. the naive persistence baseline
    forecast_rankings.csv  latest-season forecasted next-season rankings, all pools
"""

import argparse
import os
import pickle
import sys

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error
from scipy.stats import spearmanr

try:
    from xgboost import XGBRegressor
    HAS_XGBOOST = True
except ImportError:
    HAS_XGBOOST = False

import scout_engine as se

HERE = os.path.dirname(os.path.abspath(__file__))
COMPOSITE_CACHE = os.path.join(HERE, "composite_full.pkl")
MODEL_PATH = os.path.join(HERE, "forecast_model.pkl")
EVAL_PATH = os.path.join(HERE, "forecast_eval.csv")
CV_EVAL_PATH = os.path.join(HERE, "cv_eval.csv")
RANKINGS_PATH = os.path.join(HERE, "forecast_rankings.csv")

POSITIONS = ["GK", "DF", "MF", "FW"]
MIN_MINUTES = 450  # ~5 full matches; filters out noise from tiny sample sizes

# Feature set: reuses the same historical-performance signals the engine's
# own market-value model (MV_FEATURE_COLS) trusts, plus the composite index
# itself and its two sub-components (so the model can learn how last
# season's rating and its drivers translate into next season's rating).
FEATURE_COLS = [
    "age_num", "minutes", "games",
    "goals_per90", "assists_per90", "npxg_per90", "xg_assist_per90",
    "sca_per90", "tackles", "interceptions", "clearances",
    "progressive_passes", "progressive_carries",
    "power_rating", "composite_index", "zscore_comp", "style_pctile_avg",
]


def find_data_file(name):
    """The shipped layout has data/<name>, but files are sometimes dropped
    flat next to the script (as in this project) — check both."""
    for candidate in (os.path.join(HERE, "data", name), os.path.join(HERE, name)):
        if os.path.exists(candidate):
            return candidate
    raise FileNotFoundError(f"Could not find {name} in {HERE}/data/ or {HERE}/")


def load_raw():
    players_path = find_data_file("players.csv.gz")
    df = pd.read_csv(players_path, compression="gzip", low_memory=False)
    return df


def build_composite_dataset(rebuild=False):
    """Compute the engine's real composite_index for every player-season,
    within each (season, league, position) pool — exactly how the live lab
    does it — and cache the result."""
    if not rebuild and os.path.exists(COMPOSITE_CACHE):
        return pd.read_pickle(COMPOSITE_CACHE)

    print("Building composite-index dataset (first run, ~1-2 min)...")
    df = load_raw()
    df = se.standardize_positions(df)
    style_cats = se.get_playing_style_categories()

    pools = []
    for (season, league), g in df.groupby(["season", "league"]):
        for pos in POSITIONS:
            pos_df = g[g["primary_position"] == pos].copy()
            if "minutes" in pos_df.columns:
                pos_df = pos_df[se._num_series(pos_df["minutes"]).fillna(0) >= MIN_MINUTES]
            if len(pos_df) < 5:  # too small a pool for stable z-scores/percentiles
                continue
            pools.append(se.calculate_composite_index(pos_df, pos, style_cats))

    full = pd.concat(pools, ignore_index=True)
    full["season_start"] = full["season"].str[:4].astype(int)
    full["age_num"] = full["age"].apply(se.parse_age)
    full["player_key"] = (
        full["player"].astype(str).str.strip().str.lower() + "|" + full["birth_year"].astype(str)
    )
    full = full.sort_values(["player_key", "season_start"]).reset_index(drop=True)
    full.to_pickle(COMPOSITE_CACHE)
    print(f"Cached {len(full):,} player-season rows -> {COMPOSITE_CACHE}")
    return full


def build_training_frame(full):
    """Pairs each player-season with their composite_index the FOLLOWING
    season (consecutive seasons only — gap==1 — so this is a genuine
    next-season forecast, not just same-season regression)."""
    full = full.sort_values(["player_key", "season_start"]).reset_index(drop=True)
    full["next_season_start"] = full.groupby("player_key")["season_start"].shift(-1)
    full["next_composite"] = full.groupby("player_key")["composite_index"].shift(-1)
    full["gap"] = full["next_season_start"] - full["season_start"]

    train_df = full[full["gap"] == 1].copy()
    for c in FEATURE_COLS:
        train_df[c] = se._num_series(train_df[c]).fillna(0)
    return train_df


def make_xy(train_df):
    pos_dum = pd.get_dummies(train_df["primary_position"], prefix="pos")
    X = pd.concat([train_df[FEATURE_COLS], pos_dum], axis=1)
    y = train_df["next_composite"]
    return X, y


def build_candidate_models(fast=False):
    """The two 'appropriate ML techniques' compared for this task: both are
    gradient-boosted tree ensembles (well suited to tabular, mixed-scale
    sports stats), differing in regularization/optimization approach —
    a natural comparison for justifying the final model choice.
    fast=True uses fewer trees for a quicker (slightly less accurate) run."""
    n_est_gbr = 80 if fast else 200
    n_est_xgb = 120 if fast else 300
    candidates = {
        "GradientBoosting": GradientBoostingRegressor(
            n_estimators=n_est_gbr, max_depth=3, learning_rate=0.08 if fast else 0.05, random_state=42
        ),
    }
    if HAS_XGBOOST:
        candidates["XGBoost"] = XGBRegressor(
            n_estimators=n_est_xgb, max_depth=4, learning_rate=0.08 if fast else 0.05,
            subsample=0.8, colsample_bytree=0.8, random_state=42, n_jobs=-1
        )
    else:
        print("(xgboost not installed — only GradientBoosting will be evaluated; "
              "`pip install xgboost` to enable the comparison.)")
    return candidates


def train_and_evaluate(train_df, split_season=2022, fast=False):
    """Time-based split (train on seasons before split_season, test on
    split_season onward) so evaluation reflects real forecasting, not
    leakage from shuffled same-era data. Trains every candidate model,
    reports each against the naive 'next season = same as this season'
    persistence baseline, and selects the best-performing model (by
    Spearman rank correlation, since this is a RANKING task) to deploy."""
    X, y = make_xy(train_df)
    train_mask = train_df["season_start"] < split_season
    test_mask = train_df["season_start"] >= split_season

    X_train, y_train = X[train_mask], y[train_mask]
    X_test, y_test = X[test_mask], y[test_mask]
    baseline_pred_all = train_df.loc[test_mask, "composite_index"]

    candidates = build_candidate_models(fast=fast)
    fitted = {}
    rows = []

    for name, model in candidates.items():
        model.fit(X_train, y_train)
        fitted[name] = model
        pred = model.predict(X_test)

        rows.append({
            "model": name, "position": "ALL", "n_test": int(test_mask.sum()),
            "mae": round(mean_absolute_error(y_test, pred), 2),
            "spearman": round(spearmanr(y_test, pred)[0], 3),
        })
        for pos in POSITIONS:
            pos_mask = test_mask & (train_df["primary_position"] == pos)
            if pos_mask.sum() < 20:
                continue
            yp, pp = y[pos_mask], model.predict(X[pos_mask])
            rows.append({
                "model": name, "position": pos, "n_test": int(pos_mask.sum()),
                "mae": round(mean_absolute_error(yp, pp), 2),
                "spearman": round(spearmanr(yp, pp)[0], 3),
            })

    # Naive persistence baseline, same rows shape, for direct comparison.
    rows.append({
        "model": "Baseline(persistence)", "position": "ALL", "n_test": int(test_mask.sum()),
        "mae": round(mean_absolute_error(y_test, baseline_pred_all), 2),
        "spearman": round(spearmanr(y_test, baseline_pred_all)[0], 3),
    })
    for pos in POSITIONS:
        pos_mask = test_mask & (train_df["primary_position"] == pos)
        if pos_mask.sum() < 20:
            continue
        bp = train_df.loc[pos_mask, "composite_index"]
        rows.append({
            "model": "Baseline(persistence)", "position": pos, "n_test": int(pos_mask.sum()),
            "mae": round(mean_absolute_error(y[pos_mask], bp), 2),
            "spearman": round(spearmanr(y[pos_mask], bp)[0], 3),
        })

    eval_df = pd.DataFrame(rows)
    eval_df.to_csv(EVAL_PATH, index=False)
    print("\nEvaluation — all candidate models vs. naive persistence baseline:")
    print(eval_df.to_string(index=False))
    print(f"\nSaved -> {EVAL_PATH}")

    # Pick the best candidate on overall (position=ALL) Spearman — this is a
    # ranking task, so rank correlation is the primary selection criterion.
    overall = eval_df[eval_df["position"] == "ALL"]
    ml_overall = overall[overall["model"] != "Baseline(persistence)"]
    best_name = ml_overall.sort_values("spearman", ascending=False).iloc[0]["model"]
    print(f"\nBest model on overall Spearman rank correlation: {best_name}")

    # Refit the winning model type on ALL data (train+test) for deployment.
    model_full = build_candidate_models(fast=fast)[best_name]
    model_full.fit(X, y)
    importances = sorted(zip(X.columns, model_full.feature_importances_), key=lambda t: -t[1])
    print(f"\nTop feature importances ({best_name}):")
    for feat, imp in importances[:10]:
        print(f"  {feat:<20s} {imp:.3f}")

    with open(MODEL_PATH, "wb") as f:
        pickle.dump({"model": model_full, "columns": list(X.columns), "model_name": best_name}, f)
    print(f"\nSaved trained model ({best_name}) -> {MODEL_PATH}")

    return model_full, list(X.columns), eval_df


def forecast_latest_season(full, model, columns):
    """Use the most recent season available for each pool as input features
    to forecast next season's skill ranking, for every player/pool."""
    latest_per_pool = full.groupby(["league", "primary_position"])["season_start"].transform("max")
    latest = full[full["season_start"] == latest_per_pool].copy()
    for c in FEATURE_COLS:
        latest[c] = se._num_series(latest[c]).fillna(0)

    pos_dum = pd.get_dummies(latest["primary_position"], prefix="pos")
    X_latest = pd.concat([latest[FEATURE_COLS], pos_dum], axis=1)
    X_latest = X_latest.reindex(columns=columns, fill_value=0)

    latest["forecast_next_composite"] = model.predict(X_latest)
    latest["forecast_rank_in_pool"] = latest.groupby(
        ["league", "primary_position"]
    )["forecast_next_composite"].rank(ascending=False, method="min")

    out_cols = [
        "player", "team", "season", "league", "primary_position", "age_num",
        "composite_index", "forecast_next_composite", "forecast_rank_in_pool",
    ]
    result = latest[out_cols].sort_values(
        ["league", "primary_position", "forecast_rank_in_pool"]
    )
    result.to_csv(RANKINGS_PATH, index=False)
    print(f"\nSaved forecasted rankings for {len(result):,} players -> {RANKINGS_PATH}")
    return result


def cross_validate(train_df, cutoffs=(2019, 2020, 2021, 2022, 2023, 2024), fast=False):
    """Walk-forward (rolling-origin) cross-validation: for each cutoff year,
    train on every season strictly before it and test on exactly that
    season. This is the standard way to validate a forecasting model —
    it checks whether the result from a single train/test split (e.g. the
    2022 split used by default) generalizes across different points in
    time, rather than being a one-off lucky/unlucky split.
    fast=True uses fewer trees per model (~3x faster, slightly noisier)."""
    X, y = make_xy(train_df)
    candidates = build_candidate_models(fast=fast)
    rows = []
    n_cutoffs = len(cutoffs)

    for i, cutoff in enumerate(cutoffs, 1):
        train_mask = train_df["season_start"] < cutoff
        test_mask = train_df["season_start"] == cutoff
        if test_mask.sum() < 50 or train_mask.sum() < 500:
            print(f"[{i}/{n_cutoffs}] cutoff={cutoff}: skipped (not enough rows)")
            continue
        X_train, y_train = X[train_mask], y[train_mask]
        X_test, y_test = X[test_mask], y[test_mask]
        baseline_pred = train_df.loc[test_mask, "composite_index"]
        print(f"[{i}/{n_cutoffs}] cutoff={cutoff}: training on {train_mask.sum():,} rows, "
              f"testing on {test_mask.sum():,} rows...", flush=True)

        for name, model in candidates.items():
            print(f"    fitting {name}...", flush=True)
            model.fit(X_train, y_train)
            pred = model.predict(X_test)
            rows.append({
                "cutoff_season": cutoff, "model": name, "n_test": int(test_mask.sum()),
                "mae": round(mean_absolute_error(y_test, pred), 2),
                "spearman": round(spearmanr(y_test, pred)[0], 3),
            })

        rows.append({
            "cutoff_season": cutoff, "model": "Baseline(persistence)", "n_test": int(test_mask.sum()),
            "mae": round(mean_absolute_error(y_test, baseline_pred), 2),
            "spearman": round(spearmanr(y_test, baseline_pred)[0], 3),
        })

    cv_df = pd.DataFrame(rows)
    cv_df.to_csv(CV_EVAL_PATH, index=False)
    print(f"\nWalk-forward cross-validation across {len(cutoffs)} season cutoffs:")
    print(cv_df.to_string(index=False))

    summary = cv_df.groupby("model")[["mae", "spearman"]].mean().round(3)
    summary = summary.sort_values("spearman", ascending=False)
    print("\nAverage across all cutoffs (higher spearman / lower mae = better):")
    print(summary.to_string())
    print(f"\nSaved -> {CV_EVAL_PATH}")
    return cv_df


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rebuild", action="store_true", help="Rebuild the composite-index cache from scratch")
    parser.add_argument("--split-season", type=int, default=2022, help="Seasons before this year train; this year onward test")
    parser.add_argument("--cv", action="store_true", help="Run walk-forward cross-validation across multiple season cutoffs instead of a single split")
    parser.add_argument("--fast-cv", action="store_true", help="Like --cv but with fewer cutoffs (3 instead of 6) and fewer trees — ~5x faster, good for a quick sanity check on slower machines")
    parser.add_argument("--league", type=str, default=None, help="Filter printed forecast to one league, e.g. premier-league")
    parser.add_argument("--position", type=str, default=None, choices=POSITIONS, help="Filter printed forecast to one position")
    parser.add_argument("--top", type=int, default=20, help="How many rows to print for the filtered forecast")
    args = parser.parse_args()

    full = build_composite_dataset(rebuild=args.rebuild)
    train_df = build_training_frame(full)
    print(f"\n{len(train_df):,} player-seasons with a valid next-season target "
          f"(consecutive seasons only) out of {len(full):,} total player-seasons.")

    if args.cv or args.fast_cv:
        if args.fast_cv:
            cross_validate(train_df, cutoffs=(2020, 2022, 2024), fast=True)
        else:
            cross_validate(train_df)
        return

    model, columns, _ = train_and_evaluate(train_df, split_season=args.split_season)
    rankings = forecast_latest_season(full, model, columns)

    if args.league or args.position:
        view = rankings
        if args.league:
            view = view[view["league"] == args.league]
        if args.position:
            view = view[view["primary_position"] == args.position]
        print(f"\nTop {args.top} forecasted for next season "
              f"(league={args.league or 'ALL'}, position={args.position or 'ALL'}):")
        print(view.head(args.top).to_string(index=False))


if __name__ == "__main__":
    sys.exit(main())