# Rules: what the loss calculator implements, and why

Checked against primary texts on 21 Oct 2026. Copies are in `docs/sources/`. Code: `src/solarschedule/rules.py` (regimes as data) and `src/solarschedule/loss.py` (settlement). Tests: `tests/test_loss.py`.

## 1. Formula (DSM Regulations 2024, **Reg 6(2)**, not 7(2))
PLAN.md cited Regulation 7(2). The deviation formula is actually in **Regulation 6(2)**. Regulation 7 sets the Normal Rate of charges. The Karnataka HC order and the Third Amendment's Statement of Reasons (para 4.36) also refer to it as **6(2)(b)**.

- **6(2)(a), to 31.03.2026:** DWS % = 100 × (A − S) / AvC
- **6(2)(b), from 01.04.2026:** DWS % = 100 × (A − S) / [X% × AvC + (100 − X)% × S]
- AvC (Reg 3(1)(g)) = rating of the inverters able to generate in the block. In code it becomes `AvC × 0.25` MWh so the units match. CERC's own worked examples use MW throughout (2024 SOR, illustration 1: (280 − 250)/300 = 10%).

## 2. Charges (Reg 8(4) and Note-1; numbering per the Errata of 18.11.2024)
| Slab of DWS | Solar, to 31.03.2026 | Solar, from 01.04.2026 | Over-injection (received) | Under-injection (paid) |
|---|---|---|---|---|
| VLwS(1) | ≤ 10% | ≤ 5% | contract rate | contract rate |
| VLwS(2) | 10–15% | 5–10% | 90% of CR | 110% of CR |
| Beyond | > 15% | > 10% | zero | 200% of CR |

Charges are not linked to grid frequency (Reg 8(4)). The bands tighten on **01.04.2026 even though X stays at 100%** in FY 2026-27, so FY27 is already stricter than FY26.

**Slab-wise charging (interpretation).** The deviated energy is cut at the volume limits and each slice is paid at its own band's rate. In the alternative reading, one rate would apply to the whole block. Why slab-wise:
1. The 2024 table says "for VLwS(1) @ contract rate; for VLwS(2) @ 90%", where each VLwS is a range of deviation ("beyond 5% and up to 10%"). That describes volumes within ranges, not a block classification.
2. The predecessor rules (DSM 2014, Second Amendment 2015, Tables I–II) say this outright: "at the Fixed Rate for the shortfall energy for absolute error up to 15% + 110% of the Fixed Rate for **balance energy beyond 15% and up to 25%**".
3. DSM 2022 uses the same structure: "@ 90% … for deviation beyond [5%] and up to [10%]".

Slab-wise charging keeps the loss continuous in the deviation, with no cliff at a band edge. The tests pin this down: switching to whole-block charging fails 27 of 61 tests.

**Loss vs perfect schedule**, per MWh deviated: band 1 → 0; band 2 → 10% of CR; beyond → 100% of CR, **on both sides**. PLAN insight 1 (roughly symmetric ₹ loss) holds.

## 3. Open decisions, closed

### 3.1 X path → **100 / 90 / 75 / 55 / 30 / 0** (closed)
CERC order, Petition **9/SM/2025**, 31.03.2026, **para 84(a)**, solar and wind-solar hybrid, including stations aggregated through a QCA:

| FY | 26-27 | 27-28 | 28-29 | 29-30 | 30-31 | from 01.04.2031 |
|---|---|---|---|---|---|---|
| X | 100% | 90% | 75% | 55% | 30% | **0%** |

- **80/60/40/20 was the draft** of 10.09.2025 (para 7 of the order), and the Commission moved away from it on purpose (para 74). The SolarQuarter report quoted the draft. It stays in the code only as a sensitivity (`x_path="draft"`).
- PLAN.md said "0% from FY 2030-31/2031". The order says 30% in FY 2030-31 and 0% from 01.04.2031 (FY 2031-32). So the trajectory runs over **six financial years, FY27 to FY32**.
- Wind (para 84(b)): 100/95/85/65/35/0. Not used for a solar plant.
- **Para 85:** NLDC is to prepare a procedure for DWS% after 31.03.2031 "for the specific time blocks where the schedule is very small". It does not exist yet. Until it does, the code applies the literal formula: at X = 0 with S = 0, any injection is beyond VLwS(2). This is exactly the low-output-block risk in insight 3, and the memo must flag that a future NLDC procedure could soften it.

### 3.2 Third Amendment → **does not apply to an existing Pavagada plant** (closed)
CERC DSM (Third Amendment) Regulations 2026, notified 25.08.2026, **in force 31.08.2026**. New **Reg 8(4A)** puts a WS seller on General Seller charges only for:
- (a) bidding-route projects with tender or bid submission **on or after 01.01.2027**, or
- (b) other projects with **COD on or after 01.01.2029**.

The scenario plant is an existing Pavagada block, bid well before 2027 and already in commercial operation, so neither applies. The SOR (para 4.34) says the split is between projects that knew the new rules when they bid and those that did not. So the Third Amendment adds no regime for this plant. It stays a talking point: a plant bid today faces a different regime.

Also checked, and dropped from the analysis:
- The 2025 proposal for **no payment for over-injection at ≥ 50.05 Hz** (order 9/SM/2025, para 87(c)) was **not** adopted. The X order (para 106) puts it out of scope, and the Third Amendment does not include it.
- The proposal to treat existing WS sellers **at par with General Sellers from 01.04.2031** (para 87(a)) was **not** adopted either. Existing plants stay on Reg 8(4), with X = 0 from FY32.
- The Second Amendment 2025 changes only infirm-power charges (Reg 8(8)). Not relevant here.

### 3.3 Litigation → **modelled as a scenario, not a fact** (closed as a modelling decision)
| Forum | What | Status per the most recent primary source |
|---|---|---|
| **Delhi HC** | SPDA WP(C) 14783/2024, WIPPA WP(C) 5481/2025, IWPA WP(C) 5487/2025 against DSM 2024; further writs against the X proposal | Interim "no coercive steps against the petitioners" (orders of 20.11.2024 and 29.04.2025, per order 9/SM/2025 paras 34, 70). The X order says its enforcement "is subject to the outcome of the Writ Petitions … no coercive action … till continuance of the interim orders" (para 86). |
| **Karnataka HC** | NSEFI & Ors. v. Union of India, WP 13260/2026 (Justice K S Hemalekha) | Interim order of 27.04.2026: Reg 6(2)(b) and 8(4) "shall not be enforced against the petitioners", who continue under the earlier regime with a 15% band (LiveLaw, 28.04.2026). It ran to the hearing of 10.06.2026. |
| **Both** | | CERC's SOR to the Third Amendment (25.08.2026, para 4.36) says Reg 6(2)(b) and 8(4) "are under challenge before the Hon'ble High Court of Karnataka and the Hon'ble High Court of Delhi, and that interim orders have been passed". |

**Not found:** any order after 25.08.2026. A search on 21 Oct 2026 turned up no final judgment in either court. The status is "interim relief, for petitioners only, as of late August 2026", and the README must say so.

**Decision:** the **base case is the notified rules** (`solar_regime(date)`). They bind every plant that is not a petitioner, and CERC says the interim orders do not stay the Regulations (order 9/SM/2025 para 70; SOR para 4.36). **Litigation succeeds** is a sensitivity: `CERC_2014`, the DSM 2014 rules as amended in 2015. It has AvC denominator, slabs at 15/25/35%, over-injection paid at 100/90/80/70% of CR and under-injection charged at 100/110/120/130%. This is the regime the Karnataka petitioners were allowed to continue under. The "2014" label comes from the LiveLaw report; the court's order text was not available.

## 4. Scenario assumptions this rests on
- **The plant is an inter-State (ISTS-connected) regional entity.** CERC's DSM applies only to regional entities (Reg 4). Part of Pavagada Solar Park evacuates through an ISTS pooling station, and the scenario assumes the plant is one of those blocks. This is a scenario assumption, not checked against a specific plant's connectivity. A Pavagada plant connected to the state grid would be settled under **KERC's own DSM Regulations, 2026** (notified June 2026, per SolarQuarter 24.06.2026), which are not modelled. The README must state this.
- **Contract rate** = the plant's PPA tariff (Reg 3(1)(j)(i)). Still open; the range is set in milestone 5.
- **QCA pooling** (Note-2): the pool's contract rate is the weighted average of the plants' rates. The regulation does not name the weight; the code uses AvC. De-pooling (Note-2(c)) is a private QCA agreement and is not modelled.
- **DSM 2022** (05.12.2022 – 15.09.2024) is not modelled. Its under-injection charge is tied to the market Normal Rate, and no analysis applies past-dated rules. `solar_regime()` refuses dates before 16.09.2024.

## 5. Sources (all in `docs/sources/`)
- CERC (DSM and Related Matters) Regulations 2024, notification 05.08.2024: cercind.gov.in/regulations/192-Noti.pdf
- Errata, 18.11.2024 (renumbers Reg 8 clauses (15)–(18) to (1)–(4)): cercind.gov.in/regulations/192-ERRATA.pdf
- Statement of Reasons, DSM 2024: cercind.gov.in/Regulations/SOR192.pdf
- Order in Petition 9/SM/2025 (value of X), 31.03.2026: cercind.gov.in/2026/Orders/9-SM-2025.pdf
- DSM (Second Amendment) Regulations 2025: cercind.gov.in/regulations/199.pdf
- DSM (Third Amendment) Regulations 2026, 25.08.2026: cercind.gov.in/regulations/208-notification.pdf ; SOR: cercind.gov.in/regulations/208-third-amendment-for.pdf
- DSM 2014 (Second Amendment) Regulations 2015: cercind.gov.in/2015/regulation/Noti7.pdf
- DSM 2022 (checked for §2 and §4, not archived): cercind.gov.in/Regulations/168_reg.pdf
- Karnataka HC interim order, reported: https://www.livelaw.in/high-court/karnataka-high-court/karnataka-high-court-cerc-renewable-energy-generators-2014dsm-regime-532080 , https://www.mercomindia.com/karnataka-high-court-stays-cercs-revised-deviation-settlement-mechanism
- KERC DSM 2026, reported: https://solarquarter.com/2026/06/24/kerc-notifies-dsm-regulations-2026-tightens-forecasting-norms-for-solar-wind-and-hybrid-projects-in-karnataka/
