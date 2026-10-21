"""CERC deviation-settlement regimes for a solar WS seller, as data.

Every number here is taken from a primary text archived in docs/sources/ and
cited in docs/RULES.md. A regime is a setting, never an assumption baked into
the calculator: the litigation and amendment status can change, so callers
pick the regime explicitly or look it up by date.

A regime has three parts:
  * x_pct: weight of Available Capacity in the deviation denominator,
    DSM Regulations 2024, Reg 6(2)(b):
        DWS % = 100 * (A - S) / [X% * AvC + (100 - X)% * S]
    X = 100 reproduces the pre-2026 formula of Reg 6(2)(a).
  * band_limits_pct: upper edges of the volume-limit slabs (Note-1 to Reg 8(4)).
  * over_rates / under_rates: multiple of the contract rate received for
    over-injection / paid for under-injection on the energy inside each slab,
    one more entry than there are limits (the last is "beyond the last limit").
"""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Regime:
    name: str
    x_pct: float
    band_limits_pct: tuple[float, ...]
    over_rates: tuple[float, ...]
    under_rates: tuple[float, ...]
    source: str

    def __post_init__(self):
        if not 0 <= self.x_pct <= 100:
            raise ValueError(f"X must be in [0, 100], got {self.x_pct}")
        if list(self.band_limits_pct) != sorted(self.band_limits_pct):
            raise ValueError("band limits must be ascending")
        n = len(self.band_limits_pct) + 1
        if len(self.over_rates) != n or len(self.under_rates) != n:
            raise ValueError(f"need {n} rates per side, one per slab")
        # Losses vs a perfect schedule are only non-negative if over-injection
        # never earns more than the contract rate and under-injection never
        # costs less. True for every CERC regime; guard against typos.
        if any(r > 1 for r in self.over_rates) or any(r < 1 for r in self.under_rates):
            raise ValueError("over rates must be <= 1 and under rates >= 1")


# Reg 8(4), DSM Regulations 2024: (i)-(iii) over-injection, (iv)-(vi) under-injection.
_OVER_2024 = (1.0, 0.9, 0.0)
_UNDER_2024 = (1.0, 1.1, 2.0)
_SRC_2024 = "CERC DSM Regulations 2024, Reg 6(2), Reg 8(4), Note-1"

# Regulation 5(1)(v)-(vi) of DSM Regulations 2014 as amended by the Second
# Amendment 2015 (Tables I and II), in force 01.11.2015 until DSM Regulations
# 2022 took over on 05.12.2022. Kept because the Karnataka HC interim order of
# 27.04.2026 (WP 13260/2026) reportedly lets the petitioners continue under
# the "2014 regime" with a 15% band: this is the "litigation succeeds" scenario.
# (DSM 2022, in force 05.12.2022-15.09.2024, is not modelled: its
# under-injection charge is linked to the market Normal Rate, not the
# contract rate, and no analysis here needs it.)
CERC_2014 = Regime(
    name="CERC DSM 2014 (as amended 2015)",
    x_pct=100.0,
    band_limits_pct=(15.0, 25.0, 35.0),
    over_rates=(1.0, 0.9, 0.8, 0.7),
    under_rates=(1.0, 1.1, 1.2, 1.3),
    source="CERC DSM (Second Amendment) Regulations 2015, Reg 5(1)(v)-(vi), Tables I-II",
)

# 16.09.2024 to 31.03.2026: Reg 6(2)(a) (AvC denominator), Note-1(i) bands.
CERC_2024_PRE_APR2026 = Regime(
    name="CERC DSM 2024, to 31.03.2026",
    x_pct=100.0,
    band_limits_pct=(10.0, 15.0),
    over_rates=_OVER_2024,
    under_rates=_UNDER_2024,
    source=_SRC_2024 + "(i)",
)

# Value of X for solar / wind-solar hybrid, keyed by the calendar year in
# which the financial year starts (FY 2027-28 -> 2027).
# FINAL: CERC order in Petition 9/SM/2025 dated 31.03.2026, para 84(a).
# DRAFT: the 10.09.2025 proposal quoted in para 7 of the same order. It was
# not adopted; kept only as a sensitivity because some press reported it.
X_PATH_FINAL = {2026: 100.0, 2027: 90.0, 2028: 75.0, 2029: 55.0, 2030: 30.0, 2031: 0.0}
X_PATH_DRAFT = {2026: 100.0, 2027: 80.0, 2028: 60.0, 2029: 40.0, 2030: 20.0, 2031: 0.0}
X_PATHS = {"final": X_PATH_FINAL, "draft": X_PATH_DRAFT}

DSM_2024_COMMENCEMENT = date(2024, 9, 16)
X_START = date(2026, 4, 1)


def fy_start_year(on: date) -> int:
    """Indian financial year runs 1 April to 31 March."""
    return on.year if on.month >= 4 else on.year - 1


def solar_regime_for_fy(fy: int, x_path: str = "final") -> Regime:
    """Regime for a solar seller from 01.04.2026 onwards (Note-1(ii) bands)."""
    if fy < 2026:
        raise ValueError("the X trajectory starts in FY 2026-27; use solar_regime(on=...)")
    path = X_PATHS[x_path]
    x = path[min(fy, max(path))]
    return Regime(
        name=f"CERC DSM 2024, FY {fy}-{(fy + 1) % 100:02d}, X={x:g}% ({x_path} path)",
        x_pct=x,
        band_limits_pct=(5.0, 10.0),
        over_rates=_OVER_2024,
        under_rates=_UNDER_2024,
        source=_SRC_2024 + "(ii); CERC order 9/SM/2025 "
        + ("para 84(a)" if x_path == "final" else "para 7 (draft, not adopted)"),
    )


def solar_regime(on: date, x_path: str = "final") -> Regime:
    """The regime that applies on a date, as notified (ignoring court stays).

    Litigation is modelled by choosing CERC_2014 explicitly, not by date.
    The Third Amendment's Reg 8(4A) does not apply to an existing plant
    (see docs/RULES.md), so it never appears here.
    """
    if on < DSM_2024_COMMENCEMENT:
        raise ValueError(
            "dates before 16.09.2024 fall under DSM 2022, which is not modelled; "
            "pass a regime explicitly"
        )
    if on < X_START:
        return CERC_2024_PRE_APR2026
    return solar_regime_for_fy(fy_start_year(on), x_path)
