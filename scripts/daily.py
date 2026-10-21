"""Daily live job: save the latest forecast for Pavagada as it stands now.

Run by .github/workflows/daily.yml at 09:00 IST, before day-ahead gate
closure, so the forecast for tomorrow's 96 blocks is one a scheduler could
really have used. Each run gets its own folder, named by its IST issue time:

    data/live/forecast/2026-10-22T0900/minutely_15.parquet
    data/live/forecast/2026-10-22T0900/hourly.parquet

and appends one line to data/live/runs.csv. Turning these into a schedule
and scoring them against what happened is milestone 6.

    uv run python scripts/daily.py
"""

import csv
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

from solarschedule import openmeteo as om
from solarschedule.store import LIVE, write

IST = ZoneInfo(om.TZ)


def main() -> None:
    issued = datetime.now(IST).replace(second=0, microsecond=0)
    folder = LIVE / "forecast" / issued.strftime("%Y-%m-%dT%H%M")
    m15, hourly = [], []
    for m in om.MODELS:
        a, b = om.live(m)
        m15.append(a)
        hourly.append(b)
    stamp = {"issued_at_ist": issued.replace(tzinfo=None)}
    m15 = pd.concat(m15, ignore_index=True).assign(**stamp)
    hourly = pd.concat(hourly, ignore_index=True).assign(**stamp)
    write(m15, folder / "minutely_15.parquet")
    write(hourly, folder / "hourly.parquet")

    # Tomorrow's 96 blocks must be complete for every model, or the run fails
    # loudly (and the workflow shows red) rather than saving a silent hole.
    tomorrow = (pd.Timestamp(issued.date()) + pd.Timedelta(days=1)).date()
    tm = m15[m15.time_ist.dt.date == tomorrow]
    blocks = tm.groupby("model").time_ist.nunique()
    ghi_nulls = tm.groupby("model").shortwave_radiation.apply(lambda s: s.isna().sum())

    log = LIVE / "runs.csv"
    new = not log.exists()
    with log.open("a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["issued_at_ist", "model", "tomorrow", "blocks", "ghi_nulls"])
        for m in om.MODELS:
            w.writerow([issued.isoformat(timespec="minutes"), m, tomorrow, blocks.get(m, 0), ghi_nulls.get(m, "")])
    print(f"wrote {folder.relative_to(LIVE)}: {len(m15)} 15-min rows, {len(hourly)} hourly rows")
    print(pd.DataFrame({"blocks": blocks, "ghi_nulls": ghi_nulls}).to_string())

    bad = [m for m in om.MODELS if blocks.get(m, 0) != 96 or ghi_nulls.get(m, 1) > 0]
    if bad:
        raise SystemExit(f"incomplete forecast for {tomorrow}: {bad}")


if __name__ == "__main__":
    main()
