"""Weather -> AC output of the modelled 100 MW plant at Pavagada.

Two steps (docs/PLANT.md):

1. `calibrate` fits a small physical model to one Kaggle plant, where
   irradiance on the panels and module temperature are measured:

       AC per inverter = min(a * G/1000 * (1 + gamma * (T_mod - 25)), clip)
       T_mod           = T_air + G / u

   a is output at 1000 W/m2 and 25 C before clipping, so a / clip is the
   effective DC/AC ratio net of all losses. gamma is the power temperature
   coefficient, u the heat-loss factor (no wind: Kaggle has none).

2. `ac_mw` applies those shape parameters to Pavagada weather: pvlib sun
   position at the interval midpoint, plane-of-array irradiance on a fixed
   south-facing rack, module temperature, then the same power curve scaled
   to the plant's AC capacity.

Open-Meteo radiation is the mean over the interval ending at `time_ist`
(docs/DATA.md), so the sun is placed half an interval earlier.
"""

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd
import pvlib
from scipy.optimize import least_squares

from solarschedule.openmeteo import LAT, LON, TZ

CAPACITY_MW = 100.0  # AC, at the grid connection; "available capacity" in Reg 6(2)
TILT, AZIMUTH = 14.0, 180.0  # fixed rack at about latitude tilt, facing south
ALTITUDE = 575.0  # m, Open-Meteo grid cell
N_INVERTERS = 22  # per Kaggle plant


@dataclass(frozen=True)
class Params:
    a_kw: float  # AC per inverter at 1000 W/m2 and 25 C, unclipped
    gamma: float  # per C
    clip_kw: float  # AC limit per inverter
    u: float  # W/m2 per C

    @property
    def dc_ac(self) -> float:
        return self.a_kw / self.clip_kw

    def as_dict(self) -> dict:
        return asdict(self) | {"dc_ac": self.dc_ac}


def kaggle_frame(gen: pd.DataFrame, weather: pd.DataFrame, plant: int) -> pd.DataFrame:
    """One row per timestamp for one Kaggle plant.

    ac_kw is the mean over the inverters reporting, so a dropout does not
    read as low output (docs/DATA.md, Kaggle quirks). g is W/m2.
    """
    g = gen[gen.plant == plant].groupby("time_ist").agg(
        ac_kw=("ac_power", "mean"), n_inv=("source_key", "nunique")
    )
    w = weather[weather.plant == plant].set_index("time_ist")
    w = w[["irradiation", "module_temperature", "ambient_temperature"]]
    df = g.join(w, how="inner").rename(
        columns={"module_temperature": "t_mod", "ambient_temperature": "t_air"}
    )
    df["g"] = df.pop("irradiation") * 1000
    return df.reset_index()


def power_curve(g, t_mod, a_kw, gamma, clip_kw):
    dc = a_kw * np.asarray(g) / 1000 * (1 + gamma * (np.asarray(t_mod) - 25))
    return np.clip(np.minimum(dc, clip_kw), 0, None)


def module_temp(t_air, g, u):
    return t_air + g / u


def calibrate(df: pd.DataFrame, min_g: float = 20.0) -> Params:
    """Fit Params by least squares on daylight rows of `kaggle_frame`."""
    d = df[df.g > min_g].dropna(subset=["ac_kw", "g", "t_mod", "t_air"])
    hot = d[d.g > 200]
    u = float((hot.g * (hot.t_mod - hot.t_air)).sum() / ((hot.t_mod - hot.t_air) ** 2).sum())

    def resid(p):
        return power_curve(d.g.to_numpy(), d.t_mod.to_numpy(), *p) - d.ac_kw.to_numpy()

    top = d.ac_kw.max()
    fit = least_squares(resid, x0=[top, -0.004, top], bounds=([0, -0.01, 0], [5 * top, 0, 2 * top]))
    a_kw, gamma, clip_kw = fit.x
    return Params(float(a_kw), float(gamma), float(clip_kw), u)


def predict_kaggle(df: pd.DataFrame, p: Params, measured_temp: bool = True) -> pd.Series:
    t = df.t_mod if measured_temp else module_temp(df.t_air, df.g, p.u)
    return pd.Series(power_curve(df.g, t, p.a_kw, p.gamma, p.clip_kw), index=df.index)


def poa(weather: pd.DataFrame, interval: str) -> pd.Series:
    """Plane-of-array irradiance (W/m2) for weather labelled at interval end."""
    mid = pd.DatetimeIndex(weather.time_ist) - pd.Timedelta(interval) / 2
    sun = pvlib.solarposition.get_solarposition(mid.tz_localize(TZ), LAT, LON, ALTITUDE)
    dni_extra = pvlib.irradiance.get_extra_radiation(sun.index)
    irr = pvlib.irradiance.get_total_irradiance(
        TILT,
        AZIMUTH,
        sun.apparent_zenith.to_numpy(),
        sun.azimuth.to_numpy(),
        dni=weather.direct_normal_irradiance.to_numpy(),
        ghi=weather.shortwave_radiation.to_numpy(),
        dhi=weather.diffuse_radiation.to_numpy(),
        dni_extra=dni_extra.to_numpy(),
        model="haydavies",
    )
    out = np.nan_to_num(np.asarray(irr["poa_global"], dtype=float), nan=0.0)
    out = np.where(sun.apparent_zenith.to_numpy() < 90, out, 0.0)
    # keep missing inputs missing rather than zero
    out = np.where(weather.shortwave_radiation.isna().to_numpy(), np.nan, out.clip(min=0))
    return pd.Series(out, index=weather.index)


def ac_mw(weather: pd.DataFrame, p: Params, interval: str = "15min",
          capacity_mw: float = CAPACITY_MW) -> pd.Series:
    """Modelled AC output (MW, mean over each interval) for Open-Meteo weather.

    Needs time_ist, shortwave_radiation, direct_normal_irradiance,
    diffuse_radiation and temperature_2m. The Kaggle power curve is scaled so
    its clip level equals `capacity_mw`.
    """
    g = poa(weather, interval)
    t = module_temp(weather.temperature_2m, g, p.u)
    per_unit = power_curve(g, t, p.dc_ac, p.gamma, 1.0)
    return pd.Series(np.asarray(per_unit) * capacity_mw, index=weather.index)


RADIATION = {  # Open-Meteo column -> pvlib clear-sky column
    "shortwave_radiation": "ghi",
    "direct_normal_irradiance": "dni",
    "diffuse_radiation": "dhi",
}


def clearsky_15(times: pd.DatetimeIndex) -> pd.DataFrame:
    """Ineichen clear-sky GHI/DNI/DHI, mean over each 15-min block ending at `times`."""
    loc = pvlib.location.Location(LAT, LON, TZ, ALTITUDE)
    fine = pd.date_range(times.min() - pd.Timedelta("14min"), times.max(), freq="1min", tz=TZ)
    cs = loc.get_clearsky(fine).tz_localize(None)
    return cs.resample("15min", label="right", closed="right").mean().reindex(times)


def to_15min(hourly: pd.DataFrame) -> pd.DataFrame:
    """Hourly interval-mean weather -> 15-min blocks (labelled at block end).

    Radiation: the hour's clear-sky index (value / clear-sky mean over the
    hour) times the clear-sky value of each block, so the hourly energy is
    kept and the sunrise/sunset ramps follow the sun instead of stepping.
    Temperature and wind: linear in time, edge blocks held. A value labelled H covers
    (H-1h, H], i.e. the blocks ending H-45, H-30, H-15 and H.
    """
    h = hourly.set_index("time_ist").sort_index()
    t15 = pd.date_range(h.index.min() - pd.Timedelta("45min"), h.index.max(), freq="15min")
    cs = clearsky_15(t15)
    hour = t15.ceil("h")  # the hourly label each block belongs to
    out = pd.DataFrame(index=t15)
    for col, cs_col in RADIATION.items():
        cs_hour = cs[cs_col].groupby(hour).transform("mean").to_numpy()
        val = h[col].reindex(hour).to_numpy()
        k = np.where(cs_hour > 1.0, val / np.where(cs_hour > 1.0, cs_hour, 1.0), 0.0)
        out[col] = np.where(np.isnan(val), np.nan, np.clip(k, 0, 3) * cs[cs_col].to_numpy())
    for col in ("temperature_2m", "wind_speed_10m"):
        if col in h:
            s = h[col].reindex(h.index.union(t15))
            # the first three blocks precede the first label: hold its value
            out[col] = s.interpolate("time", limit_area="inside").bfill(limit=3).reindex(t15)
    return out.rename_axis("time_ist").reset_index()
