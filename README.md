# SolarSchedule

**Work in progress, shipping 7 Nov 2026.** A day-ahead solar forecast for a 100 MW plant at Pavagada, Karnataka, turned into a ₹ decision under CERC's Deviation Settlement Mechanism rules: what to schedule in each 15-minute block, what deviations will cost as the rules tighten to 2031, and whether better forecasts or a battery pay for themselves.

- Plan and scope: [`PLAN.md`](PLAN.md)
- Regulations, with citations: [`docs/RULES.md`](docs/RULES.md)
- Data sources and caveats: [`docs/DATA.md`](docs/DATA.md), gaps in [`docs/DATA_QUALITY.md`](docs/DATA_QUALITY.md)
- Progress: [`docs/PROJECT_LOG.md`](docs/PROJECT_LOG.md); where AI was wrong: [`docs/AI_LOG.md`](docs/AI_LOG.md)

A GitHub Actions job saves the day's forecast at 09:00 IST every day (`data/live/`).

```
uv sync
uv run pytest
uv run python scripts/backfill.py     # Open-Meteo history
uv run python scripts/get_kaggle.py   # needs a Kaggle token
uv run python scripts/quality.py      # DuckDB views + docs/DATA_QUALITY.md
```

Weather data by [Open-Meteo.com](https://open-meteo.com/) (CC BY 4.0).
