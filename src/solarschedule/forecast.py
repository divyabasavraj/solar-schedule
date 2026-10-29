"""Day-ahead forecasts of the 96 blocks of day D, issued at the 09:00 IST
gate on D-1, and the walk-forward backtest that scores them.

The forecast ladder (PLAN.md section 6):

  persistence  the last complete day (D-2) block by block: at the gate on
               D-1 that day is not over yet
  cloud        clear-sky output x (1 - 0.75 * cloud^3.4) (Kasten-Czeplak),
               cloud = mean day-ahead cloud cover of the three models
  nwp          day-ahead GHI/DNI/DHI/temperature of each model through the
               plant model; `nwp_mean` averages the three
  gbm          gradient-boosted trees (scikit-learn's histogram GBM, the
               LightGBM algorithm; LightGBM itself needs a system OpenMP
               library) with quantile loss on the above plus time of day,
               season and recent errors; q50 is the point forecast

Every input is one a scheduler had at the gate: day-ahead weather of the
chosen lead (docs/DATA.md, "Lead time") and actuals up to day D-2.

A block is labelled by its end (`time_ist`), like Open-Meteo; `day` is the
date of its start, so the block ending 00:00 belongs to the day before.
"""

import numpy as np
import pandas as pd

from solarschedule import plant
from solarschedule.openmeteo import MODELS

QUANTILES = (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)
SHORT = {"ecmwf_ifs025": "ecmwf", "gfs_seamless": "gfs", "icon_global": "icon"}
SEASONS = {12: "winter", 1: "winter", 2: "winter", 3: "summer", 4: "summer", 5: "summer",
           6: "monsoon", 7: "monsoon", 8: "monsoon", 9: "monsoon", 10: "post-monsoon",
           11: "post-monsoon"}


def add_day_block(df: pd.DataFrame) -> pd.DataFrame:
    start = df.time_ist - pd.Timedelta("15min")
    return df.assign(day=start.dt.normalize(), block=(start.dt.hour * 4 + start.dt.minute // 15))


def nwp_features(dayahead: pd.DataFrame, prm: plant.Params, lead: int) -> pd.DataFrame:
    """15-min modelled output and cloud cover from each model's day-ahead run."""
    out = None
    for m in MODELS:
        h = dayahead[(dayahead.model == m) & (dayahead.lead_days == lead)]
        h = h.drop(columns=["model", "lead_days"]).sort_values("time_ist")
        q = plant.to_15min(h)
        cc = h.set_index("time_ist").cloud_cover
        cc15 = cc.reindex(q.time_ist.dt.ceil("h")).to_numpy() / 100
        part = pd.DataFrame({
            "time_ist": q.time_ist,
            f"nwp_{SHORT[m]}": plant.ac_mw(q, prm).to_numpy(),
            f"cc_{SHORT[m]}": cc15,
            f"t_{SHORT[m]}": q.temperature_2m.to_numpy(),
        })
        out = part if out is None else out.merge(part, on="time_ist", how="outer")
    names = [SHORT[m] for m in MODELS]
    out["nwp_mean"] = out[[f"nwp_{n}" for n in names]].mean(axis=1)
    out["cc_mean"] = out[[f"cc_{n}" for n in names]].mean(axis=1)
    out["t_mean"] = out[[f"t_{n}" for n in names]].mean(axis=1)
    return out


def clearsky_mw(times: pd.Series, t_air: pd.Series, prm: plant.Params) -> np.ndarray:
    cs = plant.clearsky_15(pd.DatetimeIndex(times))
    w = pd.DataFrame({
        "time_ist": times.to_numpy(),
        "shortwave_radiation": cs.ghi.to_numpy(),
        "direct_normal_irradiance": cs.dni.to_numpy(),
        "diffuse_radiation": cs.dhi.to_numpy(),
        "temperature_2m": t_air.fillna(30.0).to_numpy(),
    })
    return plant.ac_mw(w, prm).to_numpy()


def build_frame(actual: pd.DataFrame, dayahead: pd.DataFrame, prm: plant.Params,
                lead: int) -> pd.DataFrame:
    """One row per block with the actual and every gate-time input."""
    df = add_day_block(actual[["time_ist", "mw"]].rename(columns={"mw": "actual"}))
    df = df.merge(nwp_features(dayahead, prm, lead), on="time_ist", how="inner")
    df = df.sort_values("time_ist", ignore_index=True)
    df["clear"] = clearsky_mw(df.time_ist, df.t_mean, prm)
    df["cloud"] = df.clear * (1 - 0.75 * df.cc_mean.clip(0, 1) ** 3.4)

    # actuals known at the gate: up to day D-2
    wide = df.pivot_table(index="day", columns="block", values="actual")
    wide = wide.reindex(pd.date_range(wide.index.min(), wide.index.max(), freq="D"))
    lag2 = wide.shift(2).stack(future_stack=True).rename("persistence")
    err = (df.pivot_table(index="day", columns="block", values="actual")
           - df.pivot_table(index="day", columns="block", values="nwp_mean")).reindex(wide.index)
    recent = err.shift(2).rolling(7, min_periods=3).mean().stack(future_stack=True).rename("recent_err")
    day_err = err.mean(axis=1).shift(2).rename("lastday_err")
    df = df.merge(lag2.reset_index().rename(columns={"level_0": "day"}), on=["day", "block"], how="left")
    df = df.merge(recent.reset_index().rename(columns={"level_0": "day"}), on=["day", "block"], how="left")
    df = df.merge(day_err.rename_axis("day").reset_index(), on="day", how="left")

    doy = df.day.dt.dayofyear
    df["doy_sin"], df["doy_cos"] = np.sin(2 * np.pi * doy / 365.25), np.cos(2 * np.pi * doy / 365.25)
    df["season"] = df.day.dt.month.map(SEASONS)
    return df


FEATURES = [
    "nwp_ecmwf", "nwp_gfs", "nwp_icon", "nwp_mean",
    "cc_ecmwf", "cc_gfs", "cc_icon", "cc_mean", "t_mean",
    "clear", "cloud", "block", "doy_sin", "doy_cos",
    "persistence", "recent_err", "lastday_err",
]

GBM = dict(max_iter=300, learning_rate=0.05, max_leaf_nodes=31, min_samples_leaf=40,
           l2_regularization=1.0, early_stopping=False, random_state=0)


def fit_quantiles(train: pd.DataFrame, quantiles=QUANTILES) -> dict:
    from sklearn.ensemble import HistGradientBoostingRegressor

    day = train[train.clear > 0]
    return {q: HistGradientBoostingRegressor(loss="quantile", quantile=q, **GBM)
            .fit(day[FEATURES], day.actual) for q in quantiles}


def predict_quantiles(models: dict, df: pd.DataFrame, capacity: float = plant.CAPACITY_MW) -> pd.DataFrame:
    """Quantile forecasts, sorted per row (no crossing), 0 at night, within [0, capacity]."""
    raw = np.column_stack([models[q].predict(df[FEATURES]) for q in sorted(models)])
    raw = np.sort(raw, axis=1).clip(0, capacity)
    raw[df.clear.to_numpy() <= 0] = 0.0
    return pd.DataFrame(raw, index=df.index, columns=[f"q{round(q * 100):02d}" for q in sorted(models)])


def walk_forward(df: pd.DataFrame, first_test: str, gap_days: int = 2) -> pd.DataFrame:
    """Refit at the start of each month on everything known by then, predict the month.

    At the gate on D-1 actuals end at D-2, so the training set for a month
    starting on day M ends `gap_days` before M.
    """
    out = []
    months = pd.date_range(pd.Timestamp(first_test), df.day.max(), freq="MS")
    for m in months:
        train = df[df.day < m - pd.Timedelta(days=gap_days - 1)]
        test = df[(df.day >= m) & (df.day < m + pd.offsets.MonthBegin(1))]
        if test.empty:
            continue
        qs = predict_quantiles(fit_quantiles(train), test)
        out.append(pd.concat([test[["time_ist", "day", "block"]], qs], axis=1))
    return pd.concat(out, ignore_index=True)
