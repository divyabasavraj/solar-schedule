"""Decision analysis on the backtest: annual Rs loss by rule year, the
schedule percentile, a battery that absorbs deviations, and pooling.

Inputs are per-block frames from scripts/backtest.py (MW, mean over the
block). Energies passed to the loss calculator are MWh per block.
Parameters and their sources are in the comments below.
"""

import numpy as np
import pandas as pd
from scipy.optimize import brentq

from solarschedule.loss import BLOCK_HOURS, settle
from solarschedule.plant import CAPACITY_MW
from solarschedule.rules import Regime

# Rs/kWh. Base: SECI's 200 MW Pavagada award to SB Energy (2018, Rs 2.82);
# high: NTPC's 2016 Pavagada awards (Rs 4.79).
CONTRACT_RATE = 2.82
CONTRACT_RANGE = (2.82, 4.79)

# Standalone 2-hour BESS tenders, Rs lakh per MW per month: 1.48 (L1 tracker,
# 2026) to 2.10 (GUVNL, VGF, Feb 2026).
BESS_RS_LAKH_PER_MW_MONTH = (1.48, 2.10)
BESS_HOURS = 2.0
ROUND_TRIP = 0.88

# QCA forecasting and scheduling fee, Rs per MW per month: GSECL's 75 MW
# solar QCA tender (2021), estimated Rs 6.96 lakh for 24 months. The only
# public per-MW figure found; awards are not published, so build vs buy is
# read as a break-even.
QCA_FEE_RS_PER_MW_MONTH = 3870


def annual_loss_lakh(df: pd.DataFrame, schedule_mw, regime: Regime,
                     rate: float = CONTRACT_RATE) -> float:
    """Rs lakh per year, scaling the days in `df` to 365."""
    r = settle(df.actual * BLOCK_HOURS, np.asarray(schedule_mw) * BLOCK_HOURS,
               CAPACITY_MW, rate, regime)
    return float(r.loss_rs.sum() / df.day.nunique() * 365 / 1e5)


def block_loss(df: pd.DataFrame, schedule_mw, regime: Regime, rate: float = CONTRACT_RATE) -> pd.Series:
    r = settle(df.actual * BLOCK_HOURS, np.asarray(schedule_mw) * BLOCK_HOURS,
               CAPACITY_MW, rate, regime)
    return pd.Series(r.loss_rs.to_numpy(), index=df.index)


def best_quantile(df: pd.DataFrame, regime: Regime, quantiles: list[str]) -> tuple[str, dict]:
    """The quantile column with the lowest annual loss on `df`, and all losses."""
    losses = {q: annual_loss_lakh(df, df[q], regime) for q in quantiles}
    return min(losses, key=losses.get), losses


def qca_saving(df: pd.DataFrame, schedule_mw, regime: Regime, cut: float) -> float:
    """Rs lakh per year saved if a QCA's error is `cut` (0-1) smaller than
    ours in every block (its schedule moved that much closer to actual)."""
    s = np.asarray(schedule_mw, dtype=float)
    better = df.actual.to_numpy() + (1 - cut) * (s - df.actual.to_numpy())
    return annual_loss_lakh(df, s, regime) - annual_loss_lakh(df, better, regime)


def qca_breakeven_cut(df: pd.DataFrame, schedule_mw, regime: Regime,
                      fee: float = QCA_FEE_RS_PER_MW_MONTH) -> float:
    """Smallest error cut (0-1) at which the saving pays a fee of `fee`
    Rs/MW/month; NaN if even a perfect forecast would not."""
    need = fee * CAPACITY_MW * 12 / 1e5
    if qca_saving(df, schedule_mw, regime, 1.0) < need:
        return float("nan")
    return float(brentq(lambda c: qca_saving(df, schedule_mw, regime, c) - need, 0.0, 1.0, xtol=1e-4))


def battery(gen_mw, sched_mw, regime: Regime, energy_mwh: float,
            hours: float = BESS_HOURS, eta: float = ROUND_TRIP,
            avc: float = CAPACITY_MW) -> tuple[np.ndarray, float]:
    """Simulate a battery behind the meter that keeps deviation inside band 1.

    Each block: if the deviation is beyond the band-1 limit, charge or
    discharge just enough to bring it back (within power and energy limits).
    Inside band 1 (no loss either way) it uses the spare room to move its
    state of charge back to half, so it is ready for the next surprise. It
    charges only from the plant. Returns (export MW per block, energy lost
    in the round trip, MWh).
    """
    gen = np.asarray(gen_mw, dtype=float) * BLOCK_HOURS
    s = np.asarray(sched_mw, dtype=float) * BLOCK_HOURS
    x = regime.x_pct / 100
    lim = (x * avc * BLOCK_HOURS + (1 - x) * s) * regime.band_limits_pct[0] / 100
    step = energy_mwh / hours * BLOCK_HOURS  # max MWh in or out per block
    e_in, e_out = np.sqrt(eta), np.sqrt(eta)
    soc, target = energy_mwh / 2, energy_mwh / 2
    export = gen.copy()
    lost = 0.0
    for i in range(len(gen)):
        dev = gen[i] - s[i]
        if dev > lim[i]:
            want = dev - lim[i]
        elif dev < -lim[i]:
            want = dev + lim[i]
        elif soc < target:  # inside band 1: charge, staying above -limit
            want = min(target - soc, dev + lim[i])
        else:  # inside band 1: discharge, staying below +limit
            want = -min(soc - target, lim[i] - dev)
        if want > 0:  # charge from the plant
            c = min(want, step, gen[i], (energy_mwh - soc) / e_in)
            soc += c * e_in
            export[i] -= c
            lost += c * (1 - e_in)
        elif want < 0:  # discharge
            d = min(-want, step, soc * e_out)
            soc -= d / e_out
            export[i] += d
            lost += d / e_out * (1 - e_out)
    return export / BLOCK_HOURS, lost


def bess_cost_lakh_per_year(energy_mwh: float, hours: float = BESS_HOURS) -> tuple[float, float]:
    mw = energy_mwh / hours
    lo, hi = BESS_RS_LAKH_PER_MW_MONTH
    return mw * lo * 12, mw * hi * 12
