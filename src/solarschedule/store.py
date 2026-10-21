"""Parquet files on disk, a DuckDB catalogue over them, and gap checks.

Parquet is the source of truth and is committed; data/solarschedule.duckdb
is a disposable catalogue of views, rebuilt by `build_db()`.
"""

from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
RAW = DATA / "raw"
LIVE = DATA / "live"
DB_PATH = DATA / "solarschedule.duckdb"

# view name -> parquet glob, relative to DATA
VIEWS = {
    "archive_hourly": "raw/openmeteo/archive/*.parquet",
    "dayahead_hourly": "raw/openmeteo/previous/*.parquet",
    "hist15": "raw/openmeteo/hist15/*.parquet",
    "live_forecast_15": "live/forecast/*/minutely_15.parquet",
    "live_forecast_hourly": "live/forecast/*/hourly.parquet",
    "kaggle_generation": "raw/kaggle/generation.parquet",
    "kaggle_weather": "raw/kaggle/weather.parquet",
}


def write(df: pd.DataFrame, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
    return path


def build_db(db_path: Path = DB_PATH) -> list[str]:
    """(Re)create one view per source that has files. Returns the views made."""
    made = []
    with duckdb.connect(str(db_path)) as con:
        for name, glob in VIEWS.items():
            if not list(DATA.glob(glob)):
                con.execute(f"DROP VIEW IF EXISTS {name}")
                continue
            pattern = (DATA / glob).as_posix()
            con.execute(
                f"CREATE OR REPLACE VIEW {name} AS "
                f"SELECT * FROM read_parquet('{pattern}', union_by_name = true)"
            )
            made.append(name)
    return made


def trim(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """Drop leading and trailing rows where every value column is null.

    Those are outside the source's coverage, not gaps. Interior nulls stay
    and are reported by scripts/quality.py.
    """
    has = df[cols].notna().any(axis=1).to_numpy()
    if not has.any():
        return df.iloc[0:0]
    first, last = has.argmax(), len(has) - 1 - has[::-1].argmax()
    return df.iloc[first : last + 1]


def find_gaps(times: pd.Series, freq: str) -> pd.DataFrame:
    """Runs of missing timestamps on a regular grid.

    Returns one row per run: start, end (inclusive) and n_missing.
    """
    t = pd.DatetimeIndex(times.dropna().unique()).sort_values()
    if t.empty:
        return pd.DataFrame(columns=["start", "end", "n_missing"])
    grid = pd.date_range(t[0], t[-1], freq=freq)
    missing = grid.difference(t)
    return runs(missing, freq)


def find_null_runs(df: pd.DataFrame, value_cols: list[str], freq: str) -> pd.DataFrame:
    """Runs of timestamps where any of `value_cols` is null."""
    bad = pd.DatetimeIndex(df.loc[df[value_cols].isna().any(axis=1), "time_ist"]).sort_values()
    return runs(bad, freq)


def runs(stamps: pd.DatetimeIndex, freq: str) -> pd.DataFrame:
    """Group sorted timestamps into consecutive runs on a `freq` grid."""
    if len(stamps) == 0:
        return pd.DataFrame(columns=["start", "end", "n_missing"])
    s = pd.Series(stamps)
    run_id = (s.diff() != pd.Timedelta(freq)).cumsum()
    g = s.groupby(run_id)
    return pd.DataFrame(
        {"start": g.min().values, "end": g.max().values, "n_missing": g.size().values}
    )
