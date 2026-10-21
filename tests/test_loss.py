"""Hand-worked tests for every band x side x regime.

Common setup unless stated: 100 MW plant, so AvC = 100 MW = 25 MWh per
15-minute block; contract rate Rs 3/kWh = Rs 3,000/MWh.
Loss per MWh deviated, by band, under DSM 2024: band 1 -> 0,
band 2 -> 10% of CR = Rs 300, beyond -> 100% of CR = Rs 3,000 (both sides).
"""

from datetime import date

import numpy as np
import pytest

from solarschedule.loss import pool, settle
from solarschedule.rules import (
    CERC_2014,
    CERC_2024_PRE_APR2026,
    Regime,
    solar_regime,
    solar_regime_for_fy,
)

AVC = 100.0
CR = 3.0


def one(actual, scheduled, regime, avc=AVC, cr=CR):
    return settle(actual, scheduled, avc, cr, regime).iloc[0]


# --- DSM 2024 up to 31.03.2026: AvC denominator, bands 10% / 15% -----------

PRE = CERC_2024_PRE_APR2026


@pytest.mark.parametrize(
    "actual, scheduled, band, dsm, loss",
    [
        # Over, band 1: dev 1 MWh = 4% of 25. Paid 1 x 3000 at CR. No loss.
        (21.0, 20.0, 0, 3000.0, 0.0),
        # Over, band 2: dev 3.5 = 14%. Slabs 2.5 @ 1.0 + 1.0 @ 0.9
        # -> 7500 + 2700 = 10200. Loss 1.0 x 300 = 300.
        (23.5, 20.0, 1, 10200.0, 300.0),
        # Over, beyond: dev 5 = 20%. Slabs 2.5 @ 1, 1.25 @ 0.9, 1.25 @ 0
        # -> 7500 + 3375 = 10875. Loss 1.25 x 300 + 1.25 x 3000 = 4125.
        (15.0, 10.0, 2, 10875.0, 4125.0),
        # Under, band 1: pay 1 x 3000. No loss.
        (20.0, 21.0, 0, -3000.0, 0.0),
        # Under, band 2: pay 2.5 x 3000 + 1.0 x 3300 = 10800. Loss 300.
        (20.0, 23.5, 1, -10800.0, 300.0),
        # Under, beyond: pay 7500 + 1.25 x 3300 + 1.25 x 6000 = 19125. Loss 4125.
        (10.0, 15.0, 2, -19125.0, 4125.0),
    ],
)
def test_pre_april_2026(actual, scheduled, band, dsm, loss):
    r = one(actual, scheduled, PRE)
    assert r.band == band
    assert r.dsm_rs == pytest.approx(dsm)
    assert r.loss_rs == pytest.approx(loss)


# --- DSM 2024 from 01.04.2026: bands 5% / 10%, each X on the final path -----
# Schedule fixed at 20 MWh so the denominator is 25X + 20(1-X) = 20 + 5X.
# Deviation is set to 3%, 8% and 15% of that denominator:
#   band 1 (3%):  loss 0
#   band 2 (8%):  slabs 5% @ 0, 3% @ 0.1 CR -> 0.03 d x 300 = 9d
#   beyond (15%): 5% @ 0, 5% @ 0.1 CR, 5% @ 1.0 CR -> 0.05 d x 3300 = 165d

X_CASES = [
    # fy,   X,    d,     band-2 loss, beyond loss
    (2026, 100.0, 25.00, 225.00, 4125.00),
    (2027, 90.0, 24.50, 220.50, 4042.50),
    (2028, 75.0, 23.75, 213.75, 3918.75),
    (2029, 55.0, 22.75, 204.75, 3753.75),
    (2030, 30.0, 21.50, 193.50, 3547.50),
    (2031, 0.0, 20.00, 180.00, 3300.00),
]


@pytest.mark.parametrize("fy, x, d, loss_b2, loss_beyond", X_CASES)
@pytest.mark.parametrize("side", [+1, -1], ids=["over", "under"])
def test_each_year_of_x_path(fy, x, d, loss_b2, loss_beyond, side):
    regime = solar_regime_for_fy(fy)
    assert regime.x_pct == x
    for frac, band, loss in [(0.03, 0, 0.0), (0.08, 1, loss_b2), (0.15, 2, loss_beyond)]:
        r = one(20.0 + side * frac * d, 20.0, regime)
        assert r.denominator_mwh == pytest.approx(d)
        assert r.deviation_pct == pytest.approx(side * frac * 100)
        assert r.band == band
        assert r.loss_rs == pytest.approx(loss)


def test_fy27_over_and_under_amounts():
    # X = 100 but the bands are already 5% / 10%: dev 3 MWh = 12% of 25.
    # Slabs 1.25 @ 1, 1.25 @ 0.9/1.1, 0.5 @ 0/2.0.
    r = one(23.0, 20.0, solar_regime_for_fy(2026))
    assert r.dsm_rs == pytest.approx(3750 + 3375)  # 7125 received
    assert r.loss_rs == pytest.approx(1.25 * 300 + 0.5 * 3000)  # 1875
    r = one(20.0, 23.0, solar_regime_for_fy(2026))
    assert r.dsm_rs == pytest.approx(-(3750 + 4125 + 3000))  # 10875 paid
    assert r.loss_rs == pytest.approx(1875)


def test_mid_trajectory_fractional_denominator():
    # FY 2029-30, X = 55: S = 10, A = 12. d = 0.55 x 25 + 0.45 x 10 = 18.25.
    # Dev 2 = 10.96% -> beyond. Edges 0.9125 and 1.825 MWh.
    # Slabs 0.9125 @ 0, 0.9125 @ 300, 0.175 @ 3000 -> 273.75 + 525 = 798.75.
    r = one(12.0, 10.0, solar_regime_for_fy(2029))
    assert r.denominator_mwh == pytest.approx(18.25)
    assert r.deviation_pct == pytest.approx(200 / 18.25)
    assert r.band == 2
    assert r.loss_rs == pytest.approx(798.75)


def test_band_edges_are_inclusive():
    # "VLwS(1) = deviation up to 5%": exactly 5% is still band 1.
    r = one(21.0, 20.0, solar_regime_for_fy(2031))  # 1 / 20 = 5%
    assert r.band == 0 and r.loss_rs == 0.0
    r = one(22.0, 20.0, solar_regime_for_fy(2031))  # 10% -> band 2
    assert r.band == 1 and r.loss_rs == pytest.approx(300.0)


def test_no_deviation_no_charge():
    r = one(20.0, 20.0, solar_regime_for_fy(2031))
    assert (r.deviation_pct, r.band, r.dsm_rs, r.loss_rs) == (0.0, 0, 0.0, 0.0)


# --- Insights 2 and 3 from PLAN.md, as tests ---------------------------------

def test_symmetric_loss_at_x100():
    # Same MWh error, schedule above or below actual: same loss when X = 100.
    regime = solar_regime_for_fy(2026)
    assert one(12.0, 10.0, regime).loss_rs == pytest.approx(one(10.0, 12.0, regime).loss_rs)


def test_lower_schedule_costs_more_once_x_falls():
    # X = 55: under-promising (S=10, A=12) vs over-promising (S=12, A=10).
    # Smaller schedule -> smaller denominator -> bigger % -> more loss.
    regime = solar_regime_for_fy(2029)
    under_promise = one(12.0, 10.0, regime).loss_rs  # d = 18.25 -> 798.75
    over_promise = one(10.0, 12.0, regime).loss_rs  # d = 19.15
    # Over-promise: edges 0.9575 / 1.915; slabs 0.9575 @ 0, 0.9575 @ 300,
    # 0.085 @ 3000 -> 287.25 + 255 = 542.25.
    assert over_promise == pytest.approx(542.25)
    assert under_promise > over_promise


def test_low_output_blocks_explode_at_x0():
    # Dawn block: S = 2, A = 3. At X = 100 that is 4% of AvC: no loss.
    assert one(3.0, 2.0, solar_regime_for_fy(2026)).loss_rs == 0.0
    # At X = 0 it is 50% of schedule. Slabs 0.1 @ 0, 0.1 @ 300, 0.8 @ 3000
    # -> 30 + 2400 = 2430.
    assert one(3.0, 2.0, solar_regime_for_fy(2031)).loss_rs == pytest.approx(2430.0)


def test_zero_schedule_at_x0_puts_everything_beyond():
    r = one(1.0, 0.0, solar_regime_for_fy(2031))
    assert r.denominator_mwh == 0.0
    assert r.deviation_pct == np.inf
    assert r.band == 2
    assert r.dsm_rs == 0.0  # over-injection beyond VLwS(2) is paid zero
    assert r.loss_rs == pytest.approx(3000.0)
    # And a night block with nothing scheduled and nothing produced is clean.
    r = one(0.0, 0.0, solar_regime_for_fy(2031))
    assert (r.deviation_pct, r.dsm_rs, r.loss_rs) == (0.0, 0.0, 0.0)


# --- Draft X path (sensitivity only) -----------------------------------------

@pytest.mark.parametrize("fy, x", [(2026, 100), (2027, 80), (2028, 60), (2029, 40), (2030, 20), (2031, 0)])
def test_draft_path_values(fy, x):
    assert solar_regime_for_fy(fy, x_path="draft").x_pct == x


def test_draft_path_settles():
    # FY 2027-28 draft X = 80: S = 20, d = 0.8 x 25 + 0.2 x 20 = 24.
    # A = 22.4: dev 2.4 = 10% -> band 2 edge. Loss 1.2 x 300 = 360.
    r = one(22.4, 20.0, solar_regime_for_fy(2027, x_path="draft"))
    assert r.denominator_mwh == pytest.approx(24.0)
    assert r.band == 1
    assert r.loss_rs == pytest.approx(360.0)


# --- DSM 2014 as amended 2015 (Karnataka HC petitioners' regime) -------------
# AvC denominator, slabs 15 / 25 / 35%. S = 10, A = 20: dev 10 = 40% of 25.
# Slabs: 3.75, 2.5, 2.5, 1.25 MWh.

def test_2014_over_all_four_bands():
    r = one(20.0, 10.0, CERC_2014)
    assert r.band == 3
    # 3.75 x 3000 + 2.5 x 2700 + 2.5 x 2400 + 1.25 x 2100 = 26625
    assert r.dsm_rs == pytest.approx(26625.0)
    # 2.5 x 300 + 2.5 x 600 + 1.25 x 900 = 3375
    assert r.loss_rs == pytest.approx(3375.0)


def test_2014_under_all_four_bands():
    r = one(10.0, 20.0, CERC_2014)
    # 3.75 x 3000 + 2.5 x 3300 + 2.5 x 3600 + 1.25 x 3900 = 33375
    assert r.dsm_rs == pytest.approx(-33375.0)
    assert r.loss_rs == pytest.approx(3375.0)


@pytest.mark.parametrize(
    "actual, band, loss",
    [
        (13.0, 0, 0.0),  # 12%: inside the 15% band
        (15.0, 1, 1.25 * 300),  # 20%: 1.25 MWh beyond 15% @ 10%
        (17.5, 2, 2.5 * 300 + 1.25 * 600),  # 30%
    ],
)
def test_2014_lower_bands(actual, band, loss):
    r = one(actual, 10.0, CERC_2014)
    assert r.band == band
    assert r.loss_rs == pytest.approx(loss)


# --- Accounting identities on random blocks ----------------------------------

@pytest.mark.parametrize(
    "regime",
    [CERC_2014, PRE] + [solar_regime_for_fy(fy) for fy in range(2026, 2032)],
    ids=lambda r: r.name,
)
def test_identities_hold_on_random_blocks(regime):
    rng = np.random.default_rng(7)
    a = rng.uniform(0, 25, 2000)
    s = rng.uniform(0, 25, 2000)
    out = settle(a, s, AVC, CR, regime)
    perfect = a * CR * 1000
    assert np.allclose(perfect - out.revenue_rs, out.loss_rs)
    assert (out.loss_rs >= -1e-9).all()
    # Loss never exceeds the whole deviated energy at the worst marginal rate.
    worst = max(1 - min(regime.over_rates), max(regime.under_rates) - 1)
    assert (out.loss_rs <= np.abs(a - s) * worst * CR * 1000 + 1e-6).all()


def test_vectorised_matches_scalar():
    regime = solar_regime_for_fy(2029)
    a, s = np.array([12.0, 10.0, 3.0]), np.array([10.0, 12.0, 2.0])
    batch = settle(a, s, AVC, CR, regime)
    for i in range(3):
        assert batch.loss_rs[i] == pytest.approx(one(a[i], s[i], regime).loss_rs)


def test_rejects_negative_inputs():
    with pytest.raises(ValueError):
        settle(-1.0, 0.0, AVC, CR, PRE)


# --- Regime lookup by date ----------------------------------------------------

@pytest.mark.parametrize(
    "on, x, bands",
    [
        (date(2024, 9, 16), 100, (10, 15)),
        (date(2026, 3, 31), 100, (10, 15)),
        (date(2026, 4, 1), 100, (5, 10)),
        (date(2027, 3, 31), 100, (5, 10)),
        (date(2027, 4, 1), 90, (5, 10)),
        (date(2029, 1, 15), 75, (5, 10)),  # FY 2028-29
        (date(2030, 12, 1), 30, (5, 10)),
        (date(2031, 3, 31), 30, (5, 10)),
        (date(2031, 4, 1), 0, (5, 10)),
        (date(2035, 6, 1), 0, (5, 10)),
    ],
)
def test_regime_by_date(on, x, bands):
    r = solar_regime(on)
    assert r.x_pct == x
    assert r.band_limits_pct == bands


def test_dates_before_dsm_2024_are_refused():
    with pytest.raises(ValueError):
        solar_regime(date(2024, 9, 15))


def test_regime_validation():
    with pytest.raises(ValueError):
        Regime("bad", 100, (5.0, 10.0), (1.0, 1.1, 0.0), (1.0, 1.1, 2.0), "")


# --- QCA aggregation (Note-2) ---------------------------------------------------

def test_pooling_nets_opposite_errors():
    # Plant 1 over by 2 MWh, plant 2 under by 2 MWh in the same block.
    regime = solar_regime_for_fy(2031)
    alone = one(12.0, 10.0, regime, avc=50, cr=3.0).loss_rs + one(8.0, 10.0, regime, avc=50, cr=2.5).loss_rs
    a, s, avc, cr = pool([[12.0], [8.0]], [[10.0], [10.0]], [[50.0], [50.0]], [3.0, 2.5])
    assert (a[0], s[0], avc[0]) == (20.0, 20.0, 100.0)
    assert cr[0] == pytest.approx(2.75)  # AvC-weighted: (50 x 3 + 50 x 2.5) / 100
    assert alone > 0
    assert settle(a, s, avc, cr, regime).loss_rs[0] == 0.0
