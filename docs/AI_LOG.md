# AI log

Where AI was used, what it got wrong, and how the error was caught.

| # | Date | AI use | What was wrong | How it was caught | Fix |
|---|---|---|---|---|---|
| 1 | 20 Oct 2026 | Summary of DSM Reg 8(4) | Said "under-producing is penalised more, so always under-promise" | Read Reg 8(4) directly: the ₹ loss against a perfect schedule is 10% / 100% of contract rate in band 2 / beyond, **on both sides** | Insight 1 rewritten; `test_symmetric_loss_at_x100` |
| 2 | 20 Oct 2026 | Plan drafting | Cited the deviation formula as "Regulation 7(2)" | Notified text: the formula is Reg **6(2)**; Reg 7 is the Normal Rate | PLAN.md and code comments corrected |
| 3 | 21 Oct 2026 | Web search summaries of the X order | Press reported two paths (90/75/55/30/0 and 80/60/40/20) | Read the order itself: 80/60/40/20 is the 10.09.2025 **draft** (para 7); the final is para 84(a) | Final path is the base case; draft kept as a sensitivity |
| 4 | 20 Oct 2026 | Plan drafting | "X = 0% from FY 2030-31/2031" | Order para 84(a): 30% in FY 2030-31, 0% from 01.04.2031 | Trajectory runs FY27–FY32; `test_regime_by_date` |
| 5 | 21 Oct 2026 | Calculator draft (date lookup) | First draft returned the DSM 2014 regime for any date before 16.09.2024 | Checked the regulations list: **DSM 2022** was in force 05.12.2022 – 15.09.2024 | Lookup now refuses those dates; `test_dates_before_dsm_2024_are_refused` |
| 6 | 21 Oct 2026 | Scenario text | Stated as fact that Pavagada blocks are ISTS-connected and gave their COD years | Not checked against a primary source this session | Reworded as a scenario assumption in RULES.md §4 |
| 7 | 20 Oct 2026 | Plan drafting | PLAN.md §4 named `shortwave_radiation_previous_day1` as "the honest day-ahead input" | Read the Previous Runs API docs: `_previous_day1` = predicted 24 h before the valid time, so afternoon blocks use a forecast issued after gate closure | Lead 2 proposed as base, lead 1 as an optimistic bound (`docs/DATA.md`) |
| 8 | 21 Oct 2026 | Data code draft | Wrote `except A, B:` (Python 3.14 syntax) in a Python 3.12 project | Read it back before running | `except (A, B):` |
| 9 | 21 Oct 2026 | Workflow | Used `astral-sh/setup-uv@v10`; the project publishes no moving major tag | Workflow run failed: "unable to find version v10" | Pinned `v10.3.0` |

## Checks on AI-written code
- Every expected value in `tests/test_loss.py` is hand-worked from the regulation text, with the arithmetic in comments.
- **Mutation check (21 Oct):** changing the band-2 over-injection rate from 0.9 to 0.8 fails 14 tests. Switching from slab-wise to whole-block charging fails 27. The tests catch both kinds of error.
- Side note from the mutation check: a same-size edit within the same second left a stale `.pyc`, and the restored code briefly looked broken. Clear `__pycache__` after in-place mutation tests.
- **Mutation check on the data tests (21 Oct):** breaking how gap runs are grouped fails 2 tests; an off-by-one in `trim` fails 1. Source restored and `__pycache__` cleared; 73 tests pass.
