# Project log

## 21 Oct 2026: Milestone 2 (data and daily cron) ✅, a day early
**Done when:** Parquet files in DuckDB with no gaps (or gaps logged); cron has run twice successfully.

- **Open-Meteo, 4.3 MB of Parquet** (`data/raw/openmeteo/`): reanalysis archive hourly 2022 → 20.10.2026; 15-min short-lead forecasts 2023 → 20.10.2026; day-ahead forecasts (leads of 1 and 2 days) for ECMWF, GFS and ICON from 19.01.2024. The archive does not go further back for radiation, so the plan's "2+ years" is about 2.75 years.
- **Kaggle:** both plants, 136k inverter rows and 6.4k sensor rows, as Parquet (git-ignored). Plant 1's dates are DD-MM-YYYY and Plant 2's are ISO; each file is parsed with an explicit format.
- **DuckDB:** `data/solarschedule.duckdb` holds 5 views over the Parquet files, rebuilt by `scripts/quality.py`.
- **Gaps logged** in `docs/DATA_QUALITY.md`. No missing timestamps in any Open-Meteo grid. Null runs:
  - ECMWF radiation starts a month after its temperature (761 h)
  - ICON is missing 77 h from 10.04.2026
  - GFS is missing 29 h of DNI/DHI from 18.04.2026
  - ECMWF lead-2 is missing 129 h of cloud cover from 17.04.2026

  Kaggle Plant 1 is missing 106 timestamps; Plant 2 has 904 timestamps with fewer than 22 inverters reporting. **Nothing filled**; handling is decided where the data is used.
- **Daily cron live:** public repo github.com/divyabasavraj/solar-schedule. The `daily-forecast` workflow runs at 03:30 UTC (09:00 IST), saves 15-min and hourly forecasts for 3 models, checks that tomorrow has 96 complete blocks, and commits to `data/live/`. **2 successful runs** (manual dispatch, 20:12 and 20:13 IST) plus 1 failure, caused by a bad action tag and fixed in the next commit. The first *scheduled* run is 22 Oct 09:00 IST. The two evening runs were issued after gate closure: keep them out of any day-ahead scoring (`issued_at_ist` is recorded).
- **12 new tests** (73 in total) for parsing, trimming, gap runs, retries and DuckDB views. All offline.
- **Found a leakage trap** (`docs/DATA.md`, "Lead time"). `_previous_day1` is the forecast made 24 h before each hour, which for afternoon blocks is *after* a 09:00 gate closure the day before. Proposed: lead 2 as the base case, lead 1 as the optimistic bound.

**Carried forward**
- Check on 22–23 Oct that the scheduled runs fire (GitHub can delay or skip scheduled runs).
- Milestone 3 must handle the Kaggle inverter dropouts (scale by inverters reporting) and the interval-end time labels (sun position at the interval midpoint).

**Next: milestone 3 (24 Oct, can start 22 Oct).** pvlib plant model calibrated on Kaggle data.

## 20–21 Oct 2026: Milestone 1 (rules and loss calculator) ✅
**Done when:** every band × side × regime has a hand-worked test that passes; open decisions on X path, amendment and litigation are closed with citations.

- Downloaded the primary texts from cercind.gov.in into `docs/sources/`: DSM 2024 with its errata and SOR, the X order 9/SM/2025, the Second and Third Amendments with the SOR, and the 2015 amendment to DSM 2014.
- **X path closed:** 100/90/75/55/30/0, order 9/SM/2025 para 84(a). 80/60/40/20 was the draft.
- **Third Amendment closed:** in force 31.08.2026. Reg 8(4A) covers only bids from 01.01.2027 or COD from 01.01.2029, so it does not apply to an existing plant.
- **Litigation closed as a modelling decision:** base case = the notified rules; "litigation succeeds" = DSM 2014 regime. Status checked up to CERC's SOR of 25.08.2026; nothing later found.
- **Interpretation decided:** charges are slab-wise. The 2015 text says so explicitly, and DSM 2022 and 2024 keep the same structure.
- Built `rules.py` (regimes as data, lookup by date or FY, final and draft paths) and `loss.py` (vectorised settlement, ₹ loss vs perfect schedule, QCA pooling).
- **61 tests pass**, covering each band × side for: DSM 2014, DSM 2024 before Apr 2026, each of the six FYs on the final path, and the draft path. Also covered: accounting identities on random blocks, band edges, zero schedule at X = 0, date lookup, pooling. Mutation-checked.
- Corrections to PLAN.md: formula is Reg 6(2), not 7(2); X = 0 from 01.04.2031, not FY 2030-31; bands tighten in FY27 even with X = 100.

**Carried forward**
- Contract-rate range for Pavagada PPAs (needed by milestone 5).
- Re-check court status before shipping (week of 4 Nov).
- The NLDC procedure for small-schedule blocks after 2031 (order para 85) could change insight 3; watch for it.

**Next: milestone 2 (22–23 Oct).** Open-Meteo archive and day-ahead pulls, Kaggle data, start the daily cron.
