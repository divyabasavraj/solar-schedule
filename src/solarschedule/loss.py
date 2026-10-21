"""Per-block deviation settlement and Rs loss versus a perfect schedule.

Conventions
-----------
* actual and scheduled are energies in MWh for one 15-minute block.
* avc is Available Capacity in MW (Reg 3(1)(g)); it is turned into the block's
  energy-equivalent, avc * 0.25 MWh, so that every term in the denominator
  is in MWh. This matches CERC's own worked examples, which work in MW
  throughout (2024 Statement of Reasons, illustration 1: (280-250)/300).
* contract_rate is in Rs/kWh, as defined in Reg 3(1)(j).

Charging is slab-wise: the deviated energy is cut at the volume limits and
each slice is paid at its own band's rate. The 2015 amendment states this
in words ("balance energy beyond 15% and up to 25%"); the 2024 tables keep
the same "for deviation up to / beyond and up to" structure. See docs/RULES.md.

Loss versus a perfect schedule
------------------------------
With a perfect schedule (S = A) the plant earns A * CR. With a deviation:
  over-injection:  earns S * CR + sum(slice * over_rate * CR)
  under-injection: earns S * CR - sum(slice * under_rate * CR)
so loss = sum(slice * (1 - over_rate)) * CR  or  sum(slice * (under_rate - 1)) * CR.
"""

import numpy as np
import pandas as pd

from .rules import Regime

BLOCK_HOURS = 0.25
KWH_PER_MWH = 1000.0


def settle(actual, scheduled, avc, contract_rate, regime: Regime) -> pd.DataFrame:
    """Settle each block under `regime`. Inputs broadcast like numpy arrays.

    Returns one row per block with:
      deviation_mwh   actual - scheduled (positive = over-injection)
      denominator_mwh X% * AvC + (100-X)% * S, in MWh
      deviation_pct   100 * deviation / denominator (+/-inf if denominator is 0)
      band            0-based slab of the last MWh deviated (0 = VLwS(1));
                      len(band_limits_pct) means "beyond the last limit"
      dsm_rs          deviation charge, + received by the plant, - paid
      revenue_rs      scheduled energy at contract rate + dsm_rs
      loss_rs         revenue with a perfect schedule minus revenue_rs (>= 0)
    """
    a, s, avc, cr = np.broadcast_arrays(
        *(np.asarray(v, dtype=float) for v in (actual, scheduled, avc, contract_rate))
    )
    if (a < 0).any() or (s < 0).any() or (avc < 0).any():
        raise ValueError("actual, scheduled and avc must be non-negative")

    x = regime.x_pct / 100.0
    denom = x * avc * BLOCK_HOURS + (1.0 - x) * s
    dev = a - s
    abs_dev = np.abs(dev)

    # Slab edges in MWh. When the denominator is 0 (only possible at X = 0
    # with a zero schedule) every edge is 0, so all deviated energy falls in
    # the last slab. CERC order 9/SM/2025 para 85 asks NLDC for a procedure
    # for such blocks after 31.03.2031; until it exists this is the literal
    # reading. See docs/RULES.md.
    edges = np.multiply.outer(denom, np.array(regime.band_limits_pct) / 100.0)
    lower = np.concatenate([np.zeros(denom.shape + (1,)), edges], axis=-1)
    upper = np.concatenate([edges, np.full(denom.shape + (1,), np.inf)], axis=-1)
    slab_mwh = np.clip(abs_dev[..., None] - lower, 0.0, upper - lower)

    over = dev > 0
    rates = np.where(over[..., None], regime.over_rates, regime.under_rates)
    charge_mwh = (slab_mwh * rates).sum(axis=-1)
    loss_mwh = (slab_mwh * np.abs(1.0 - rates)).sum(axis=-1)

    rs_per_mwh = cr * KWH_PER_MWH
    dsm_rs = np.where(over, charge_mwh, -charge_mwh) * rs_per_mwh

    with np.errstate(divide="ignore", invalid="ignore"):
        pct = np.where(dev == 0, 0.0, 100.0 * dev / denom)
    band = np.searchsorted(np.array(regime.band_limits_pct), np.abs(pct), side="left")

    return pd.DataFrame(
        {
            "actual_mwh": a.ravel(),
            "scheduled_mwh": s.ravel(),
            "deviation_mwh": dev.ravel(),
            "denominator_mwh": denom.ravel(),
            "deviation_pct": pct.ravel(),
            "band": band.ravel(),
            "dsm_rs": dsm_rs.ravel(),
            "revenue_rs": (s * rs_per_mwh + dsm_rs).ravel(),
            "loss_rs": (loss_mwh * rs_per_mwh).ravel(),
        }
    )


def pool(actuals, schedules, avcs, contract_rates):
    """Aggregate WS sellers at a pooling station through a QCA (Note-2 to Reg 8(4)).

    actuals, schedules and avcs hold one array per plant, aligned block by
    block; contract_rates holds one PPA rate per plant. Returns (actual,
    scheduled, avc, contract_rate) for the pool, ready for settle().
    The pool's contract rate is the weighted average of the plants' rates
    (Note-2(a)). The Regulation does not say weighted by what; this uses
    Available Capacity (a documented assumption). De-pooling back to plants
    is left to the QCA (Note-2(c)) and is not modelled.
    """
    avc_arr = np.asarray(avcs, dtype=float)
    rates = np.asarray(contract_rates, dtype=float)[:, None]
    total_avc = avc_arr.sum(axis=0)
    with np.errstate(divide="ignore", invalid="ignore"):
        cr = np.where(total_avc > 0, (rates * avc_arr).sum(axis=0) / total_avc, rates.mean())
    return (
        np.asarray(actuals, dtype=float).sum(axis=0),
        np.asarray(schedules, dtype=float).sum(axis=0),
        total_avc,
        cr,
    )
