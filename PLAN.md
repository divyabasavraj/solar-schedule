# SolarSchedule: Plan

> A day-ahead solar generation forecast for an Indian solar plant, turned into a ₹ decision: what to promise the grid in each 15-minute block to keep deviation charges under CERC's DSM rules as low as possible, how those charges will grow as the rules tighten to 2031, and whether paying for better forecasts or a battery is worth it.

## 1. The business situation
Every grid-connected solar plant must tell the grid a day ahead how much power it will produce in each **15-minute block** (96 blocks a day). If actual output is different, the plant pays or loses money through **deviation charges**.

CERC's **DSM Regulations, 2024** (verified from the notified text, cercind.gov.in/regulations/192-Noti.pdf, Regulation 6(2) and 8(4)) and CERC's **order of 31.03.2026 on "X"** (Petition 9/SM/2025) tighten this in steps. Full detail and citations: `docs/RULES.md`.

**Deviation formula for wind/solar (WS) sellers**
- Until 31.03.2026: deviation % = 100 × (actual − scheduled) / available capacity
- From 01.04.2026: deviation % = 100 × (actual − scheduled) / [X% × available capacity + (100 − X)% × scheduled]

**Volume limits for a solar plant (Note-1)**
| Period | Band 1 (VLwS1) | Band 2 (VLwS2) |
|---|---|---|
| Until 31.03.2026 | up to 10% | 10–15% |
| From 01.04.2026 | up to 5% | 5–10% |

**Charges (Regulation 8(4), not linked to grid frequency)**
| Band | Over-injection (plant receives) | Under-injection (plant pays) |
|---|---|---|
| Band 1 | contract rate | contract rate |
| Band 2 | 90% of contract rate | 110% of contract rate |
| Beyond band 2 | **zero** | **200% of contract rate** |

Charges are **slab-wise**: each slice of the deviated energy is paid at its own band's rate (the 2015 predecessor text says so explicitly; see `docs/RULES.md` §2). The bands tighten on 01.04.2026 even though X stays at 100% that year.

**X trajectory for solar (verified: order 9/SM/2025, para 84(a)):** 100% in FY 2026-27 (no change to the formula in year one), then 90% (FY 27-28), 75% (28-29), 55% (29-30), 30% (30-31), and **0% from 01.04.2031 (FY 2031-32)**, when deviation is measured fully against the schedule. The 80/60/40/20 path reported by one outlet was the 10.09.2025 **draft** (para 7), not adopted; kept as a sensitivity only. Wind has a slower path (100/95/85/65/35/0).

**Litigation and amendments (checked 21 Oct 2026, see `docs/RULES.md` §3):**
- **Delhi High Court:** writs against DSM 2024 and the X proposal; interim "no coercive steps" for the petitioners. The X order is enforceable subject to their outcome (para 86)
- **Karnataka High Court** (WP 13260/2026, NSEFI & Ors.): interim order of 27.04.2026 not to enforce Reg 6(2)(b) and 8(4) **against the petitioners**, who stay on the 2014 regime (15% band). CERC's SOR of 25.08.2026 confirms that interim orders are in place in both courts. No later order found
- **Third Amendment** (in force 31.08.2026): new Reg 8(4A) puts only projects bid from 01.01.2027 or commissioned from 01.01.2029 on General Seller charges. **Does not apply to an existing Pavagada plant**
- **Modelling decision:** base case = the notified rules; "litigation succeeds" = DSM 2014 regime, as a sensitivity

Plants either forecast in-house or pay a **Qualified Coordinating Agency (QCA)** such as REConnect Energy or Tata Power Trading.

## 2. The decision
**Scenario:** I am the data analyst for the CFO / Head of Asset Management of a company that owns a **100 MW solar plant at Pavagada Solar Park, Karnataka**.
**Their brief:** "The DSM rules keep tightening. Tell me what deviations cost us now and through 2031, how to cut that, and whether to pay a QCA or buy a battery."

| Question | Answer |
|---|---|
| Who is deciding? | CFO / Head of Asset Management |
| What are they deciding? | 1) How to set the daily schedule. 2) Build forecasting in-house or pay a QCA. 3) Whether a battery to absorb deviations pays back. 4) How exposed the plant is as X falls to 0 |
| What are the options? | Schedule = median forecast vs a higher or lower percentile; in-house model vs QCA at ₹Z/MW/month; no battery vs 5 / 10 / 20 MWh |
| What does the data say? | Forecast error per block → deviation % → band → ₹ loss, per year of the X trajectory |
| Recommendation and its value? | e.g. "Our model cuts deviation losses from ₹A to ₹B lakh/year; by FY 2030-31 the same error costs ₹C lakh, so a battery of N MWh pays back from year M" |
| How will we know it worked? | Live daily forecasts scored every week; loss estimate updated monthly |

## 3. The key insights (to prove with numbers)
1. **Loss is measured against perfect scheduling.** In band 1 the plant loses nothing (it is paid or pays at contract rate). In band 2 it loses 10% of the contract rate on the deviating energy. Beyond band 2 it loses 100%, on **either side**: over-injection is paid zero, and under-injection costs 200% instead of 100%. So in ₹ terms the bands are roughly **symmetric**, and "always under-promise" is not automatically right.
2. **The formula creates the asymmetry as X falls.** Once the denominator includes the schedule itself, a lower schedule makes the same MWh error a bigger %, pushing more blocks into expensive bands. The optimal schedule percentile therefore **shifts as X falls** from 100% to 0%. The schedule optimiser finds the optimal percentile for each year and season.
3. **Low-output blocks become dangerous at X = 0.** Early morning, late evening and cloudy blocks have a small schedule, so even small MWh errors become huge percentages. Expect most future losses to come from these blocks, which is where a battery or better short-horizon forecasting earns its money.
4. **The cost grows every year to 2031** even if forecast accuracy stays the same: the "cost of standing still" is a number the CFO needs.

**What the numbers said (milestone 5, `docs/ANALYSIS.md`):**
- Insight 2 holds, but it is small. The out-of-sample best year-round percentile moves from the median (FY26-27) to P60 (FY31-32), and the seasonal optimiser saves only 1–10 lakh a year over the median. Scheduling the median is nearly as good.
- Insight 3 is **not supported as written**. Blocks scheduled below 20 MW carry 0.6% of the loss now and 6.3% at X = 0. The shoulder hours' share doubles (15% → 32%), but midday still costs most, and about 60% of the loss falls in the monsoon. Cloudy days drive the loss, not small schedules.
- Insight 4 holds: with the same forecast, the loss grows from ₹202 lakh (FY26-27) to ₹360 lakh (FY31-32).

## 4. Data (all free)
| Data | What it gives | Use | Status |
|---|---|---|---|
| **Open-Meteo Previous Runs API** | Hourly forecasts as they stood 24 h (`_previous_day1`) or 48 h (`_previous_day2`) before each hour; ECMWF, GFS and ICON | The honest day-ahead input, the main source of forecast error. **Lead 1 leaks for blocks after gate closure**: `docs/DATA.md` | ✅ Pulled: from 19.01.2024 (radiation not archived earlier) |
| **Open-Meteo Historical Forecast API** | Archived forecasts at **15-minute** resolution | 15-min block features | ✅ Pulled: 2023 → yesterday |
| **Open-Meteo Archive API** | Actual past weather (reanalysis), many years | "What really happened" for long backtests | ✅ Pulled: 2022 → yesterday |
| **Kaggle "Solar Power Generation Data"** | **Two real Indian solar plants**, 34 days, 15-min, inverter-level power + plant sensors | Calibrate the sunlight → power model; real noise and losses | ✅ Downloaded (git-ignored; plant location not given) |
| **Mendeley: India demand, solar, wind (Sep 2021 – Jun 2025), Grid-India** | Real hourly all-India solar generation | Sanity-check seasonality and forecast skill on real grid output | ✅ Exists |
| **CERC DSM Regulations, 2024** + **CERC order on X (31.03.2026)** + Third Amendment | Formula, bands, rates, trajectory | Loss calculator | ✅ All read and archived (milestone 1) |
| Contract rate | Pavagada PPA tariff | ₹ conversion | Parameter (₹/kWh, with a sensitivity range) |

**Plant output (honest labelling):** Pavagada output is **modelled**: actual site sunlight and temperature (Open-Meteo archive) → `pvlib` plant model calibrated on the Kaggle real-plant data → 15-min MWh. The README states this clearly. The forecast error studied (day-ahead weather forecast vs what happened) is real.

## 5. Loss calculator
✅ **Built in milestone 1:** `src/solarschedule/rules.py`, `src/solarschedule/loss.py`, 61 tests in `tests/test_loss.py`.
- Implements Regulation 6(2), 8(4) and Note-1 exactly, per 15-min block: deviation %, band, ₹ received/paid, and **₹ loss vs perfect schedule**
- **Regimes as settings:** pre-01.04.2026 rules; from 01.04.2026 with X for each year of the trajectory (100 → 90 → 75 → 55 → 30 → 0); the draft 80/60/40/20 path; the DSM 2014 regime (litigation scenario). The Third Amendment does not apply to this plant
- **QCA aggregation (Note-2):** optional netting with a second plant at the same pooling station
- Unit tests with hand-worked examples for every band and side

## 6. Forecasting (about 30% of the effort)
Day-ahead forecast of 96 blocks for tomorrow, using only information available at scheduling time.

| Step | Model | Why |
|---|---|---|
| 1 | **Persistence:** tomorrow = today | The number to beat |
| 2 | **Clear-sky × forecast cloud factor** | Simple, explainable physics baseline |
| 3 | **Day-ahead weather forecast → plant model** (`pvlib`) | What a plant gets almost for free |
| 4 | **Gradient-boosted trees** (scikit-learn HistGradientBoosting; LightGBM would not load on macOS) on day-ahead weather forecasts, sun position, time of day, season, recent errors, with **quantile versions** (10th–90th percentile) | The ML model, and the forecast ranges the optimiser needs |

- **Testing:** walk-forward backtest over 2+ years (train on the past, test on the next month, roll forward); never a random split
- **Metrics:** MAE and RMSE as % of capacity, error by season (monsoon vs dry), and **₹ deviation loss**, which is what matters
- **Explainability:** SHAP / feature importance (e.g. "cloud-cover forecast error explains most monsoon losses")

## 7. Decision analysis (about 70% of the effort)
1. **Cost now and to 2031:** annual ₹ deviation loss for the 100 MW plant for each year of the X trajectory, with today's best model → the "cost of standing still"
2. **Schedule optimiser:** the forecast percentile that minimises expected ₹ loss, by season and by year of the trajectory (insight 2), vs simply promising the median
3. **Where the money goes:** loss by time of day and season (insight 3)
4. **Build vs buy:** ₹ saved by each model step; break-even error improvement a QCA must deliver to justify ₹Z/MW/month
5. **Battery sizing:** a simple battery that absorbs over-injection and covers under-injection: ₹ loss avoided for 5 / 10 / 20 MWh, per year of the trajectory, vs battery cost (published Indian BESS tender prices) → payback year
6. **Aggregation:** ₹ saved by netting with a neighbouring plant through a QCA pooling station
7. **Sensitivity:** results under the draft X path, a range of contract rates, and the DSM 2014 regime (if the litigation succeeds). Third Amendment: only as a note on what a plant bid from 2027 would face

## 8. Live part
- **Daily (GitHub Actions cron, free):** fetch tomorrow's Open-Meteo forecast for Pavagada → publish the 96-block forecast and recommended schedule
- **Next day:** fetch what happened → modelled actual output → deviation, band and ₹ loss for yesterday under current rules (and under the FY 2030-31 rules, to show future exposure)
- **Weekly report:** error, ₹ loss vs baseline, worst blocks and why ("unexpected afternoon clouds on Tuesday cost ₹1.2 lakh"); code calculates, AI writes, code checks every number
- **Monthly memo:** running ₹ total, whether the schedule percentile should change for the coming season, decision updates
- **Dashboard:** Streamlit on Hugging Face Spaces (Power BI optional for the static analysis)

## 9. Checked AI (and the AI log)
| AI use | Check |
|---|---|
| AI drafts code for the loss calculator | Unit tests with hand-worked examples from the regulation |
| AI writes weekly/monthly text | Every number must match computed results; regenerate once, then template |
| AI summarises regulations and orders | Every claim cited to a clause or order paragraph; checked against the text |

`docs/AI_LOG.md` and `docs/PROJECT_LOG.md` as in the other projects. First AI-log entry: an early summary said "under-producing is penalised more, so always under-promise"; reading Regulation 8(4) showed the ₹ loss is roughly symmetric and the real asymmetry comes from the X formula.

## 10. Tech stack (₹0)
Python 3.12, `uv`, DuckDB + Parquet, `pvlib`, LightGBM, SHAP, statsmodels, Open-Meteo APIs, GitHub Actions cron, Streamlit on HF Spaces (Power BI Desktop optional).

## 11. Milestones (full scope, ship by 7 Nov 2026)
Full scope, nothing cut. About 15 working days across 20 Oct – 7 Nov, with 2 days of buffer at the end.

| # | What | Dates | Done when |
|---|---|---|---|
| 1 ✅ | **Rules:** fetch CERC's X order and the Third Amendment, confirm X path and litigation status; build the loss calculator + unit tests (done 21 Oct; see `docs/PROJECT_LOG.md`) | 20–21 Oct | Every band × side × regime has a hand-worked test that passes; open decisions on X path, amendment and litigation are closed with citations |
| 2 ✅ | **Data:** pull 2+ years of Open-Meteo archive + day-ahead forecasts for Pavagada; download Kaggle plant data; **start the daily cron** (done 21 Oct; first scheduled run 22 Oct 09:00 IST) | 22–23 Oct | Parquet files in DuckDB with no gaps (or gaps logged); cron has run twice successfully |
| 3 ✅ | **Plant model:** `pvlib` calibrated on Kaggle data; data-quality report | 24 Oct | Calibration error reported; data-quality report written |
| 4 ✅ | **Forecast ladder + walk-forward backtest** (done 28 Oct; `docs/BACKTEST.md`) | 25–27 Oct | All 4 models backtested walk-forward; MAE/RMSE/₹ loss table by season; SHAP plot |
| 5 ✅ | **Decision analysis:** cost to 2031, schedule optimiser, where the money goes, build vs buy, battery, aggregation, sensitivity (done 29 Oct; `docs/ANALYSIS.md`) | 28 Oct – 1 Nov | All 7 analyses have a ₹ number and a chart; the numbers for A, B, C, D, M and W in section 13 are filled in |
| 6 | **Live loop:** daily forecast, next-day scoring, weekly report (AI-written, code-checked) | 2–3 Nov | First weekly report generated automatically from ~10 days of live data, every number checked |
| 7 | **Ship:** decision memo, Streamlit dashboard, README (decision and ₹ answer first), AI log, limitations | 4–5 Nov | Dashboard live on HF Spaces; memo reviewed end to end |
| — | **Buffer + final review + LinkedIn post** | 6–7 Nov | Fresh-eyes read of README and memo; post published |

Starting the cron in milestone 2 means about two weeks of real live forecasts have been scored by launch, which gives the live part real numbers to show.

## 12. Limitations (state in README)
- Plant output at Pavagada is **modelled**, not metered; the Kaggle plants are real but cover only 34 days and their location is unknown
- Open-Meteo reanalysis is not on-site measurement; real plants use their own sensors and satellite nowcasts
- Rules are under litigation and amendment; regimes are settings, not assumptions baked into the code
- Battery model is simplified (no degradation, simple round-trip efficiency)
- QCA fees vary; build-vs-buy is a break-even, not a quote
- Contract rate is a parameter; results shown across a range

## 13. Interview story
"CERC is tightening deviation rules for solar plants every year until 2031, and it's being fought in court. I modelled a 100 MW plant at Pavagada and built a day-ahead forecast, from a persistence baseline up to a quantile gradient-boosted model, tested walk-forward over two years. Then I turned it into decisions. With the free weather forecast, deviation losses are ₹316 lakh a year now (A); my model cuts that to ₹201 lakh (B), a 36% cut (D), and the cut grows to 41% by 2031, when the free forecast would cost ₹607 lakh against my ₹356 lakh (C). I expected the losses to move to low-output blocks as X falls; the data said no. Cloudy monsoon days carry 60% of the loss, and small schedules only 6%. A QCA is worth its fee only if it beats my error by about 11% (W), and a deviation-only battery never pays back (M): storage would have to get 60% cheaper. Pooling with a neighbour saves at most 9%. If the court case succeeds, the loss falls to ₹14 lakh and none of this matters, which is why the regime is a setting, not an assumption. It runs live every day and scores itself."

Sources for every number: `data/derived/headline.json`, generated by `scripts/analysis.py`.

## 14. Open decisions
- [x] X path: 100/90/75/55/30/0 (order 9/SM/2025 para 84(a)); 80/60/40/20 was the draft
- [x] Third Amendment (31.08.2026): does not apply to an existing plant (Reg 8(4A) covers only bids from 01.01.2027 or COD from 01.01.2029)
- [x] Litigation: interim relief for petitioners only, as of CERC's SOR of 25.08.2026; modelled as the DSM 2014 sensitivity. **Re-check before shipping**
- [ ] QCA fee: only public per-MW figure is GSECL's 2021 tender estimate (₹3,870/MW/month); build vs buy is shown as a break-even curve
- [ ] Plant is assumed ISTS-connected (CERC DSM); if state-connected, KERC DSM 2026 would apply instead (state in README)
- [x] Contract rate range for Pavagada PPAs: ₹2.82/kWh base (SECI 2018 award to SB Energy), ₹4.79 high (NTPC 2016 awards)
- [ ] Dashboard: Streamlit (proposed) vs Power BI
- [x] Backtest lead time: `_previous_day2` as base, `_previous_day1` as optimistic bound (decided in milestone 4)

## 15. Sources
- **Primary texts, read directly and archived in `docs/sources/`; full list in `docs/RULES.md` §5**
- CERC (Deviation Settlement Mechanism and Related Matters) Regulations, 2024: https://www.cercind.gov.in/regulations/192-Noti.pdf (Regulation 6(2), 8(4), Note-1, Note-2)
- CERC order on X, Petition 9/SM/2025, 31.03.2026: https://cercind.gov.in/2026/Orders/9-SM-2025.pdf
- DSM (Third Amendment) Regulations, 2026: https://cercind.gov.in/regulations/208-notification.pdf
- Press reports (superseded by the primary texts above):
- X trajectory: https://powerpeakdigest.com/cerc-sets-phased-x-factor-reduction-for-re-deviation-keeps-fy27-unchanged/ , https://www.energetica-india.net/news/cerc-notifies-phased-x-factor-reduction-for-wind-and-solar-tightens-deviation-bands-from-april-2026 , https://solarquarter.com/2026/04/01/cerc-announces-phased-dsm-reform-for-wind-and-solar-tightens-deviation-norms-by-2031/ , https://www.mondaq.com/india/renewables/1779874/
- Delhi HC writs: https://psuwatch.com/newsupdates/cerc-tightens-dsm-for-wind-and-solar-generators-writ-petitions-challenge-order-in-delhi-hc
- Karnataka HC interim relief: https://www.mercomindia.com/karnataka-high-court-stays-cercs-revised-deviation-settlement-mechanism , https://www.amsshardul.com/?p=19153
- Third Amendment: https://www.mvapulse.com/cerc-amends-deviation-settlement-rules-for-wind-and-solar/ , https://powerpeakdigest.com/cerc-third-dsm-amendment-wind-solar-ess-projects/
- Prayas submission on X: https://energy.prayaspune.org/our-work/policy-regulatory-engagements/wind-solar-deviation-formula
