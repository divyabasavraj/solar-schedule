"""Open-Meteo weather for the Pavagada site, as tidy DataFrames.

Three historical sources and one live one (see docs/DATA.md):

* archive      ERA5 reanalysis, hourly: "what happened"
* previous     Previous Runs API, hourly: the forecast as it stood 1 or 2
               days before each hour. The honest day-ahead input.
* hist15       Historical Forecast API, 15-minute: short-lead forecasts
               stitched together; a 15-minute view of "what happened"
* live         Forecast API: tomorrow's forecast, fetched by the daily job

Time convention: every timestamp is naive IST (Asia/Kolkata, no DST), the
clock DSM blocks are defined in. Open-Meteo radiation is the mean over the
interval *ending* at the timestamp (hourly: preceding hour; 15-minute:
preceding 15 minutes). The column `time_ist` keeps that label as is.
"""

import time
from datetime import date

import pandas as pd
import requests

LAT, LON = 14.25, 77.45
TZ = "Asia/Kolkata"

# GHI, DNI and DHI plus temperature and wind are what pvlib needs; cloud
# cover is a forecast feature.
VARS = [
    "shortwave_radiation",
    "direct_normal_irradiance",
    "diffuse_radiation",
    "temperature_2m",
    "wind_speed_10m",
    "cloud_cover",
]
VARS_15 = [v for v in VARS if v != "cloud_cover"]  # not offered at 15 min

# Global models with day-ahead radiation archived from early 2024 at this
# site. best_match resolves to gfs_seamless here, so it is not pulled again.
MODELS = ["ecmwf_ifs025", "gfs_seamless", "icon_global"]
LEADS = [1, 2]  # previous_day1, previous_day2

URLS = {
    "archive": "https://archive-api.open-meteo.com/v1/archive",
    "previous": "https://previous-runs-api.open-meteo.com/v1/forecast",
    "hist15": "https://historical-forecast-api.open-meteo.com/v1/forecast",
    "live": "https://api.open-meteo.com/v1/forecast",
}


def _get(url: str, params: dict, tries: int = 4) -> dict:
    base = {"latitude": LAT, "longitude": LON, "timezone": TZ}
    for attempt in range(tries):
        try:
            r = requests.get(url, params=base | params, timeout=120)
            if r.status_code == 200:
                return r.json()
            if r.status_code not in (429, 500, 502, 503, 504):
                raise RuntimeError(f"{url} -> {r.status_code}: {r.text[:300]}")
        except (requests.ConnectionError, requests.Timeout):
            if attempt == tries - 1:
                raise
        time.sleep(10 * 2**attempt)
    raise RuntimeError(f"{url}: gave up after {tries} tries")


def _frame(payload: dict, key: str) -> pd.DataFrame:
    df = pd.DataFrame(payload[key])
    df["time"] = pd.to_datetime(df["time"])
    return df.rename(columns={"time": "time_ist"})


def archive(start: date, end: date) -> pd.DataFrame:
    """ERA5 reanalysis, hourly, wide: time_ist + VARS."""
    p = {"hourly": ",".join(VARS), "start_date": str(start), "end_date": str(end)}
    return _frame(_get(URLS["archive"], p), "hourly")


def previous(start: date, end: date, model: str) -> pd.DataFrame:
    """Day-ahead forecasts, hourly, long: time_ist, model, lead_days + VARS.

    lead_days = 1 is the run issued about 24 h before the hour, 2 about 48 h.
    Which one a scheduler at gate closure could really have used is decided
    in milestone 4 (docs/DATA.md, "Lead time").
    """
    cols = [f"{v}_previous_day{d}" for d in LEADS for v in VARS]
    p = {
        "hourly": ",".join(cols),
        "models": model,
        "start_date": str(start),
        "end_date": str(end),
    }
    wide = _frame(_get(URLS["previous"], p), "hourly")
    parts = []
    for d in LEADS:
        part = wide[["time_ist"] + [f"{v}_previous_day{d}" for v in VARS]]
        part = part.rename(columns={f"{v}_previous_day{d}": v for v in VARS})
        parts.append(part.assign(model=model, lead_days=d))
    return pd.concat(parts, ignore_index=True)


def hist15(start: date, end: date) -> pd.DataFrame:
    """Short-lead forecasts at 15 minutes, wide: time_ist + VARS_15."""
    p = {"minutely_15": ",".join(VARS_15), "start_date": str(start), "end_date": str(end)}
    return _frame(_get(URLS["hist15"], p), "minutely_15")


def live(model: str, forecast_days: int = 3) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Latest forecast from today 00:00 IST: (15-minute frame, hourly frame).

    `model` is tagged on both frames. 15-minute values are native for some
    models and interpolated by Open-Meteo for others; the hourly frame keeps
    the native resolution for comparison with the archive.
    """
    p = {
        "models": model,
        "minutely_15": ",".join(VARS_15),
        "hourly": ",".join(VARS),
        "forecast_days": forecast_days,
    }
    j = _get(URLS["live"], p)
    return (
        _frame(j, "minutely_15").assign(model=model),
        _frame(j, "hourly").assign(model=model),
    )
