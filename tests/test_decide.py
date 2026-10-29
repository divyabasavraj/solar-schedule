"""Battery and decision helpers, with hand-worked blocks."""

import numpy as np
import pandas as pd
import pytest

from solarschedule import decide
from solarschedule.rules import solar_regime_for_fy

FY27 = solar_regime_for_fy(2026)  # X = 100, band 1 = 5% of 100 MW x 0.25 h = 1.25 MWh
FY32 = solar_regime_for_fy(2031)  # X = 0


def test_battery_absorbs_over_injection_beyond_band_1():
    # gen 60 MW vs schedule 50 MW: 2.5 MWh over, limit 1.25 -> charge 1.25 MWh
    export, lost = decide.battery([60.0], [50.0], FY27, energy_mwh=10)
    assert export[0] == pytest.approx(55.0)  # back on the band-1 edge
    assert lost == pytest.approx(1.25 * (1 - np.sqrt(0.88)))


def test_battery_covers_shortfall_within_power_limit():
    # 10 MWh / 2 h = 5 MW = 1.25 MWh per block. Shortfall 40 MW = 10 MWh,
    # 8.75 beyond the limit: discharge capped at 1.25 MWh -> export +5 MW
    export, _ = decide.battery([10.0], [50.0], FY27, energy_mwh=10)
    assert export[0] == pytest.approx(15.0)


def test_battery_rebalances_only_inside_band_1():
    # SoC starts at half; a perfect block leaves it alone
    export, lost = decide.battery([50.0, 50.0], [50.0, 50.0], FY27, energy_mwh=10)
    assert np.allclose(export, 50.0) and lost == 0


def test_battery_never_charges_from_grid():
    export, _ = decide.battery([0.0], [0.0], FY32, energy_mwh=10)
    assert export[0] >= 0


def test_battery_cuts_loss_on_noisy_days():
    rng = np.random.default_rng(1)
    n = 96 * 30
    sched = np.tile(np.clip(80 * np.sin(np.linspace(0, np.pi, 96)), 0, None), 30)
    gen = np.clip(sched + rng.normal(0, 6, n) * (sched > 0), 0, 100)
    df = pd.DataFrame({"actual": gen, "day": np.repeat(np.arange(30), 96)})
    base = decide.annual_loss_lakh(df, sched, FY32)
    export, _ = decide.battery(gen, sched, FY32, energy_mwh=20)
    assert decide.annual_loss_lakh(df.assign(actual=export), sched, FY32) < base


def test_bess_cost_two_hour():
    lo, hi = decide.bess_cost_lakh_per_year(10)  # 5 MW
    assert lo == pytest.approx(5 * 1.48 * 12) and hi == pytest.approx(5 * 2.10 * 12)
