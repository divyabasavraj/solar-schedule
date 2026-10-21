# Project log

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
