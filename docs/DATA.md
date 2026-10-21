# Data

What each dataset is, where it came from, and the traps in using it. Gap and null counts are in `DATA_QUALITY.md` (generated, do not edit).

## Layout
```
data/raw/openmeteo/archive/{year}.parquet           hourly reanalysis, 2022 ->
data/raw/openmeteo/hist15/{year}.parquet            15-min short-lead forecasts, 2023 ->
data/raw/openmeteo/previous/{model}_{year}.parquet  hourly day-ahead forecasts, Jan 2024 ->
data/raw/kaggle/{generation,weather}.parquet        two real plants, 34 days (git-ignored)
data/live/forecast/{issued IST}/...                 written by the daily job
data/live/runs.csv                                  one line per model per daily run
data/solarschedule.duckdb                           views over all of the above (git-ignored, rebuilt)
```
Rebuild everything: `uv run python scripts/backfill.py && uv run python scripts/get_kaggle.py && uv run python scripts/quality.py`. Kaggle needs a token in `~/.kaggle/`.

## Conventions
- **Time:** naive IST (Asia/Kolkata, no DST), the clock DSM blocks use. Column `time_ist`.
- **Interval labels:** Open-Meteo radiation is the mean over the interval *ending* at the timestamp (hourly: the preceding hour; 15-min: the preceding 15 minutes). A DSM block 10:00–10:15 is the 15-min row stamped 10:15. Sun position for pvlib must be taken at the interval midpoint, not the label.
- **Site:** 14.25 N, 77.45 E (Pavagada Solar Park). Open-Meteo snaps to its nearest grid cell: archive and hist15 resolve to 14.24 N, 77.44 E, 575 m; ECMWF to 14.25 N, 77.50 E.
- **Units:** W/m² (radiation), °C, km/h (wind at 10 m), % (cloud cover).

## Sources

| Source | API | Resolution | Coverage | Role |
|---|---|---|---|---|
| Archive | archive-api.open-meteo.com, default (best_match) reanalysis | hourly | 2022-01-01 → yesterday | "What happened": the weather that drives modelled actual output |
| Historical forecast | historical-forecast-api.open-meteo.com, best_match | 15 min | 2023-01-01 → yesterday | 15-min shape of "what happened" (short-lead forecasts stitched together; not a measurement) |
| Day-ahead | previous-runs-api.open-meteo.com, `_previous_day1/2` | hourly | from 19.01.2024 (GFS, ICON), 06.03.2024 (ECMWF radiation) | The forecast available before scheduling: the honest model input |
| Live | api.open-meteo.com | 15 min + hourly | from first cron run, 21.10.2026 | Daily forecasts for the live loop |
| Kaggle "Solar Power Generation Data" (anikannal) | kagglehub | 15 min | 15.05.2020 → 17.06.2020 | Two real Indian plants: calibrate weather → power |

Models for the day-ahead and live data: `ecmwf_ifs025`, `gfs_seamless`, `icon_global`. `best_match` resolves to `gfs_seamless` at this site (checked: identical coverage), so it is not pulled separately.

**Why day-ahead starts in 2024:** Open-Meteo archives most models' previous runs only from January 2024 (Previous Runs API docs). Radiation forecasts before 19.01.2024 come back null; only GFS temperature goes further back. That gives about 2.75 years of honest day-ahead input, which meets the plan's "2+ years".

## Lead time: a leakage trap (decide in milestone 4)
The Previous Runs API defines `_previous_day1` as "the value predicted 24 hours before valid time", and `_previous_day2` as 48 hours before. The offset is fixed per hour; it is not "yesterday's run".

A day-ahead schedule for day D is due on the morning of D-1 (the daily job assumes 09:00 IST). For a block at hour H on day D:
- `previous_day1` was issued at about H on D-1. **For every block after 09:00 that is after gate closure**, so a backtest on lead 1 uses information the scheduler did not have, and looks too good.
- `previous_day2` was issued at about H on D-2: always before gate closure. It is honest but a little stale, with a lead of 33–57 h against about 15–39 h in practice.

**Proposed for milestone 4:** lead 2 as the base case for the backtest, lead 1 reported as an optimistic bound. The truth lies between them; the live loop (09:00 IST forecasts) measures it directly. If the gap matters to a decision, the Single Runs API (`&run=`) can rebuild the exact 00 UTC run for each day.

## Kaggle quirks
- Plant 1 generation file writes dates as `DD-MM-YYYY HH:MM`; the other three files use `YYYY-MM-DD HH:MM:SS`. Each file is parsed with an explicit format (`scripts/get_kaggle.py`). Letting pandas guess would swap day and month for 1–12 May.
- Plant 1 `DC_POWER` is about 10× `AC_POWER`, a known units issue; use AC power.
- Each plant has 22 inverters. Plant 1 is missing 106 timestamps and Plant 2 is missing 5. Plant 2 has 904 timestamps with fewer than 22 inverters reporting. **Summing inverters naively would undercount output**: milestone 3 must scale by the number reporting, or drop those timestamps.
- Plant location is not given, and the data is 2020. It is used only for the *shape* of weather → power (losses, temperature effect, clipping), not as Pavagada output.

## Licences
- Open-Meteo data: CC BY 4.0. Credit "Weather data by Open-Meteo.com" in the README and dashboard. Free API tier for non-commercial use.
- Kaggle data: not redistributed; the repo holds only the download script.
