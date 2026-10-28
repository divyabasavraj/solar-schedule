"""Plant model: power curve, calibration on synthetic data, Pavagada weather path."""

import numpy as np
import pandas as pd
import pytest

from solarschedule import plant

P = plant.Params(a_kw=1200.0, gamma=-0.004, clip_kw=1000.0, u=30.0)


def test_power_curve_hand_worked():
    # 800 W/m2 at 45 C: 1200 * 0.8 * (1 - 0.004*20) = 960 * 0.92 = 883.2
    assert plant.power_curve(800, 45, 1200, -0.004, 1000) == pytest.approx(883.2)
    # 1000 W/m2 at 25 C: 1200 unclipped -> clipped to 1000
    assert plant.power_curve(1000, 25, 1200, -0.004, 1000) == pytest.approx(1000)
    assert plant.power_curve(0, 25, 1200, -0.004, 1000) == 0


def test_dc_ac_is_unclipped_over_clip():
    assert P.dc_ac == pytest.approx(1.2)


def test_calibrate_recovers_known_parameters():
    rng = np.random.default_rng(0)
    g = rng.uniform(0, 1100, 3000)
    t_air = rng.uniform(22, 38, 3000)
    t_mod = plant.module_temp(t_air, g, P.u)
    ac = plant.power_curve(g, t_mod, P.a_kw, P.gamma, P.clip_kw) + rng.normal(0, 5, 3000)
    df = pd.DataFrame({"g": g, "t_air": t_air, "t_mod": t_mod, "ac_kw": ac})
    fit = plant.calibrate(df)
    assert fit.a_kw == pytest.approx(P.a_kw, rel=0.01)
    assert fit.gamma == pytest.approx(P.gamma, abs=0.0003)
    assert fit.clip_kw == pytest.approx(P.clip_kw, rel=0.005)
    assert fit.u == pytest.approx(P.u, rel=0.001)


def clear_day_hourly():
    t = pd.date_range("2025-03-21 01:00", "2025-03-22 00:00", freq="h")
    cs = plant.clearsky_15(pd.date_range(t[0] - pd.Timedelta("45min"), t[-1], freq="15min"))
    hourly = cs.resample("h", label="right", closed="right").mean().reindex(t)
    return pd.DataFrame({
        "time_ist": t,
        "shortwave_radiation": hourly.ghi.to_numpy(),
        "direct_normal_irradiance": hourly.dni.to_numpy(),
        "diffuse_radiation": hourly.dhi.to_numpy(),
        "temperature_2m": 30.0,
        "wind_speed_10m": 10.0,
    })


def test_to_15min_keeps_hourly_energy_and_has_96_blocks():
    h = clear_day_hourly()
    q = plant.to_15min(h)
    assert len(q) == 96
    back = q.set_index("time_ist").shortwave_radiation.resample("h", label="right", closed="right").mean()
    assert np.allclose(back.to_numpy(), h.shortwave_radiation.to_numpy(), atol=1.0)


def test_pavagada_output_zero_at_night_and_within_capacity():
    q = plant.to_15min(clear_day_hourly())
    mw = plant.ac_mw(q, P)
    hour = q.time_ist.dt.hour
    assert (mw[(hour < 5) | (hour >= 20)] == 0).all()
    assert mw.max() <= plant.CAPACITY_MW + 1e-9
    assert mw.max() > 80  # clear equinox noon on a 1.2 DC/AC plant is near clipping


def test_missing_weather_stays_missing():
    q = plant.to_15min(clear_day_hourly())
    q.loc[48, "shortwave_radiation"] = np.nan
    assert np.isnan(plant.ac_mw(q, P)[48])
