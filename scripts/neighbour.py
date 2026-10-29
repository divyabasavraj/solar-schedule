"""A second 100 MW plant for the pooling analysis (PLAN.md section 7.6).

    uv run python scripts/neighbour.py

Same plant model and forecast ladder as the main plant, at 14.10 N,
77.28 E, about 25 km south-west: the nearest point whose Open-Meteo weather
comes from a different grid cell. Plants pooled under Note-2 must share a
pooling station, which would be closer than this, so the pooling benefit
found here is an upper bound. Writes

  data/raw/openmeteo_neighbour/{hist15,previous}/...
  data/derived/actual_15_neighbour.parquet
  data/derived/backtest_neighbour_lead2.parquet
"""

from datetime import date, timedelta

import pandas as pd

from solarschedule import forecast as fc
from solarschedule import openmeteo as om
from solarschedule import plant
from solarschedule.store import DATA, RAW, trim, write

SITE = (14.10, 77.28)
RAW_N = RAW / "openmeteo_neighbour"
OUT = DATA / "derived"


def fetch(today: date) -> tuple[pd.DataFrame, pd.DataFrame]:
    # openmeteo reads the site from module globals at call time
    om.LAT, om.LON = SITE
    h15, prev = [], []
    for y in range(2023, today.year + 1):
        a, b = date(y, 1, 1), min(date(y, 12, 31), today - timedelta(days=1))
        path = RAW_N / f"hist15/{y}.parquet"
        if not path.exists():
            write(trim(om.hist15(a, b), om.VARS_15), path)
        h15.append(pd.read_parquet(path))
        if y < 2024:
            continue
        for m in om.MODELS:
            path = RAW_N / f"previous/{m}_{y}.parquet"
            if not path.exists():
                df = om.previous(a, b, m)
                df = pd.concat([trim(g, om.VARS) for _, g in df.groupby("lead_days")], ignore_index=True)
                write(df, path)
            prev.append(pd.read_parquet(path))
    return pd.concat(h15, ignore_index=True), pd.concat(prev, ignore_index=True)


def main() -> None:
    import json

    p = json.loads((OUT / "plant_params.json").read_text())
    prm = plant.Params(p["a_kw"], p["gamma"], p["clip_kw"], p["u"])
    end = pd.read_parquet(OUT / "actual_15.parquet").time_ist.max().date() + timedelta(days=1)
    h15, prev = fetch(end)
    actual = h15[["time_ist"]].assign(mw=plant.ac_mw(h15, prm))
    write(actual, OUT / "actual_15_neighbour.parquet")
    df = fc.build_frame(actual, prev, prm, lead=2)
    preds = fc.walk_forward(df, "2024-07-01")
    res = preds.merge(df[["time_ist", "actual", "season", "clear", "nwp_mean"]], on="time_ist", how="left")
    write(res, OUT / "backtest_neighbour_lead2.parquet")
    print(len(res), res.day.min(), res.day.max())


if __name__ == "__main__":
    main()
