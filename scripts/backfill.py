"""Pull the historical Open-Meteo data for Pavagada into data/raw/openmeteo/.

One Parquet file per source, model and calendar year. Finished years are
skipped on re-runs; the current year is always refreshed.

    uv run python scripts/backfill.py
"""

import sys
from datetime import date, timedelta

import pandas as pd

from solarschedule import openmeteo as om
from solarschedule.store import RAW, trim, write

# Archive from 2022 gives the plant model a longer weather record; day-ahead
# radiation at this site is archived only from 19.01.2024 (docs/DATA.md).
START = {"archive": 2022, "hist15": 2023, "previous": 2024}


def years(source: str, today: date):
    for y in range(START[source], today.year + 1):
        yield y, date(y, 1, 1), min(date(y, 12, 31), today - timedelta(days=1))


def main() -> None:
    today = date.today()
    jobs = []
    for y, a, b in years("archive", today):
        jobs.append((RAW / f"openmeteo/archive/{y}.parquet", lambda a=a, b=b: om.archive(a, b), om.VARS))
    for y, a, b in years("hist15", today):
        jobs.append((RAW / f"openmeteo/hist15/{y}.parquet", lambda a=a, b=b: om.hist15(a, b), om.VARS_15))
    for m in om.MODELS:
        for y, a, b in years("previous", today):
            jobs.append(
                (RAW / f"openmeteo/previous/{m}_{y}.parquet", lambda a=a, b=b, m=m: om.previous(a, b, m), om.VARS)
            )

    for path, fetch, cols in jobs:
        current = str(today.year) in path.stem
        if path.exists() and not current:
            print(f"skip  {path.relative_to(RAW)}")
            continue
        df = fetch()
        if "lead_days" in df:
            df = pd.concat(
                [trim(g, cols) for _, g in df.groupby("lead_days", sort=True)], ignore_index=True
            )
        else:
            df = trim(df, cols)
        if df.empty:
            print(f"empty {path.relative_to(RAW)} (outside coverage)")
            continue
        write(df, path)
        print(f"wrote {path.relative_to(RAW)}  {len(df):>6} rows  {df.time_ist.min()} .. {df.time_ist.max()}")


if __name__ == "__main__":
    sys.exit(main())
