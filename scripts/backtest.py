"""Milestone 4: walk-forward backtest of the forecast ladder.

    uv run python scripts/backtest.py [--reuse] [lead ...]

--reuse rescores saved per-block forecasts instead of refitting (minutes).

For each lead (2 = base, 1 = optimistic bound; docs/DATA.md) builds the
gate-time inputs, refits GBM quantile models at the start of every
month from July 2024 on everything known by then, and scores all models on
the same blocks. Writes

  data/derived/backtest_lead{1,2}.parquet  per-block actual and forecasts
  docs/BACKTEST.md                         tables (generated, do not edit)
  docs/figures/shap_lead2.png              SHAP importance, final q50 model
"""

import json
import sys

import numpy as np
import pandas as pd

from solarschedule import forecast as fc
from solarschedule import plant
from solarschedule.decide import CONTRACT_RATE
from solarschedule.loss import settle
from solarschedule.rules import solar_regime_for_fy
from solarschedule.store import DATA, RAW, ROOT, write

OUT = DATA / "derived"
FIRST_TEST = "2024-07-01"
POINT = ["persistence", "cloud", "nwp_ecmwf", "nwp_gfs", "nwp_icon", "nwp_mean", "q50"]
LABEL = {"persistence": "1 Persistence (D-2)", "cloud": "2 Clear-sky x cloud",
         "nwp_ecmwf": "3 NWP ECMWF -> plant", "nwp_gfs": "3 NWP GFS -> plant",
         "nwp_icon": "3 NWP ICON -> plant", "nwp_mean": "3 NWP mean -> plant",
         "q50": "4 GBM q50 (quantile trees)"}


def load_params() -> plant.Params:
    p = json.loads((OUT / "plant_params.json").read_text())
    return plant.Params(p["a_kw"], p["gamma"], p["clip_kw"], p["u"])


def load_inputs():
    actual = pd.read_parquet(OUT / "actual_15.parquet")
    files = sorted((RAW / "openmeteo" / "previous").glob("*.parquet"))
    dayahead = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    return actual, dayahead


def run(lead: int, actual, dayahead, prm, reuse: bool = False) -> pd.DataFrame:
    df = fc.build_frame(actual, dayahead, prm, lead)
    saved = OUT / f"backtest_lead{lead}.parquet"
    if reuse and saved.exists():
        return pd.read_parquet(saved), df
    preds = fc.walk_forward(df, FIRST_TEST)
    keep = ["time_ist", "actual", "season", "clear"] + POINT[:-1]
    res = preds.merge(df[keep], on="time_ist", how="left")
    # a scheduler must send all 96 blocks: drop days that are not complete
    full = res.groupby("day").time_ist.transform("size") == 96
    res = res[full & res[POINT[:-1]].notna().all(axis=1)].reset_index(drop=True)
    return res, df


def error_table(res: pd.DataFrame, by: str | None = None) -> pd.DataFrame:
    d = res[res.clear > 0]
    rows = []
    groups = [("all", d)] if by is None else list(d.groupby(by))
    for g, part in groups:
        for m in POINT:
            e = part[m] - part.actual
            rows.append({by or "set": g, "model": LABEL[m],
                         "MAE %cap": round(e.abs().mean(), 2),
                         "RMSE %cap": round(float(np.sqrt((e**2).mean())), 2),
                         "bias %cap": round(e.mean(), 2)})
    return pd.DataFrame(rows)


def loss_table(res: pd.DataFrame) -> pd.DataFrame:
    """Rs lakh per year if each model's forecast is the schedule, by FY rules."""
    days = res.day.nunique()
    rows = []
    for m in POINT:
        row = {"model": LABEL[m]}
        for fy in (2026, 2028, 2031):
            r = settle(res.actual * 0.25, res[m] * 0.25, plant.CAPACITY_MW, CONTRACT_RATE,
                       solar_regime_for_fy(fy))
            row[f"FY{fy % 100}-{fy % 100 + 1} (X={solar_regime_for_fy(fy).x_pct:.0f})"] = round(
                r.loss_rs.sum() / days * 365 / 1e5, 1)
        rows.append(row)
    return pd.DataFrame(rows)


def coverage(res: pd.DataFrame) -> pd.DataFrame:
    d = res[res.clear > 0]
    qs = [c for c in res if c.startswith("q")]
    return pd.DataFrame([{"quantile": q, "share of actuals below": round((d.actual <= d[q]).mean(), 3)}
                         for q in qs])


def shap_plot(df: pd.DataFrame, path):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import shap

    m = fc.fit_quantiles(df[df.day < df.day.max() - pd.Timedelta(days=1)], quantiles=(0.5,))[0.5]
    day = df[df.clear > 0].sample(5000, random_state=0)
    sv = shap.TreeExplainer(m).shap_values(day[fc.FEATURES])
    imp = pd.Series(np.abs(sv).mean(axis=0), index=fc.FEATURES).sort_values()
    fig, ax = plt.subplots(figsize=(7, 5.2), facecolor="#fcfcfb")
    ax.set_facecolor("#fcfcfb")
    ax.barh(imp.index, imp.values, color="#2a78d6", height=0.6)
    ax.tick_params(colors="#52514e", labelsize=9)
    ax.set_xlabel("Mean |SHAP value| (MW per block)")
    ax.set_title("What drives the GBM median forecast", loc="left", fontsize=12, color="#0b0b0b")
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color("#c9c8c3")
    ax.grid(axis="x", color="#e6e5e0", linewidth=0.6)
    ax.set_axisbelow(True)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150)
    return imp.sort_values(ascending=False).round(2)


def main() -> None:
    prm = load_params()
    actual, dayahead = load_inputs()
    reuse = "--reuse" in sys.argv[1:]
    leads = [int(a) for a in sys.argv[1:] if a.isdigit()] or [2, 1]
    md = ["# Backtest (generated by scripts/backtest.py; do not edit)", "",
          f"Walk-forward: GBM refit at the start of each month from {FIRST_TEST} on all days known at the gate, "
          "then used for the whole month. Errors are on daylight blocks, in % of the 100 MW capacity "
          f"(= MW). ₹ loss uses the notified rules at a contract rate of ₹{CONTRACT_RATE}/kWh with the model's "
          "forecast as the schedule (q50 for GBM).", ""]
    for lead in leads:
        res, df = run(lead, actual, dayahead, prm, reuse)
        write(res, OUT / f"backtest_lead{lead}.parquet")
        tag = "base: issued ~48 h ahead, always before the gate" if lead == 2 else \
            "optimistic bound: afternoon blocks use runs issued after the gate"
        md += [f"## Lead {lead} ({tag})", "",
               f"{res.day.nunique()} complete days, {res.day.min():%d %b %Y} to {res.day.max():%d %b %Y}.", "",
               "### Error, all daylight blocks", "", error_table(res).drop(columns="set").to_markdown(index=False), "",
               "### ₹ deviation loss, lakh per year (schedule = forecast)", "", loss_table(res).to_markdown(index=False), ""]
        if lead == 2:
            by_season = error_table(res, "season").pivot(index="model", columns="season", values="MAE %cap")
            md += ["### MAE by season (% of capacity)", "",
                   by_season[["winter", "summer", "monsoon", "post-monsoon"]].reset_index().to_markdown(index=False), "",
                   "### Quantile calibration (GBM)", "", coverage(res).to_markdown(index=False), ""]
            imp = shap_plot(df, ROOT / "docs" / "figures" / "shap_lead2.png")
            md += ["### SHAP: mean |contribution| to q50 (MW), final model", "",
                   "![SHAP importance](figures/shap_lead2.png)", "",
                   imp.rename_axis("feature").reset_index(name="mean |SHAP| MW").to_markdown(index=False), ""]
    (ROOT / "docs" / "BACKTEST.md").write_text("\n".join(md))
    print("\n".join(md))


if __name__ == "__main__":
    main()
