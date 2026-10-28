"""Offline tests for the data layer: Open-Meteo parsing, trimming, gap finding.

No network: Open-Meteo responses are small hand-built payloads in the shape
the API returns (checked against live responses on 21 Oct 2026).
"""

import pandas as pd
import pytest

from solarschedule import openmeteo as om
from solarschedule import store
from solarschedule.store import find_gaps, find_null_runs, runs, trim


def ts(*s):
    return pd.to_datetime(list(s))


# --- gap and null runs -------------------------------------------------------


def test_no_gaps_on_complete_grid():
    t = pd.Series(pd.date_range("2025-01-01", periods=96, freq="15min"))
    assert find_gaps(t, "15min").empty


def test_gaps_are_grouped_into_runs():
    full = pd.date_range("2025-01-01 00:00", "2025-01-01 05:00", freq="1h")
    # drop 01:00 alone, and 03:00 + 04:00 together
    t = pd.Series(full.delete([1, 3, 4]))
    g = find_gaps(t, "1h")
    assert g.n_missing.tolist() == [1, 2]
    assert g.start.tolist() == list(ts("2025-01-01 01:00", "2025-01-01 03:00"))
    assert g.end.tolist() == list(ts("2025-01-01 01:00", "2025-01-01 04:00"))


def test_gaps_ignore_duplicates_and_order():
    t = pd.Series(ts("2025-01-01 02:00", "2025-01-01 00:00", "2025-01-01 00:00"))
    g = find_gaps(t, "1h")
    assert g.start.tolist() == list(ts("2025-01-01 01:00")) and g.n_missing.tolist() == [1]


def test_null_runs_any_column():
    df = pd.DataFrame(
        {
            "time_ist": pd.date_range("2025-01-01", periods=5, freq="1h"),
            "a": [1, None, None, 4, 5],
            "b": [1, 2, 3, 4, None],
        }
    )
    assert find_null_runs(df, ["a"], "1h").n_missing.tolist() == [2]
    assert find_null_runs(df, ["a", "b"], "1h").n_missing.tolist() == [2, 1]
    assert find_null_runs(df, ["b"], "1h").start.tolist() == list(ts("2025-01-01 04:00"))


def test_runs_empty():
    assert runs(pd.DatetimeIndex([]), "1h").empty


# --- trim ----------------------------------------------------------------------


def test_trim_drops_only_leading_and_trailing_all_null_rows():
    df = pd.DataFrame(
        {
            "time_ist": pd.date_range("2025-01-01", periods=6, freq="1h"),
            "a": [None, None, 1, None, 3, None],
            "b": [None, 5, None, None, None, None],
        }
    )
    out = trim(df, ["a", "b"])
    # row 1 has b, so coverage starts there; row 3 is an interior gap and stays
    assert out.time_ist.dt.hour.tolist() == [1, 2, 3, 4]


def test_trim_all_null_gives_empty():
    df = pd.DataFrame({"time_ist": pd.date_range("2025-01-01", periods=2, freq="1h"), "a": [None, None]})
    assert trim(df, ["a"]).empty


# --- Open-Meteo parsing ----------------------------------------------------------


def hourly_payload(cols, n=3):
    return {
        "timezone": "Asia/Kolkata",
        "hourly": {"time": [f"2025-05-01T{h:02d}:00" for h in range(n)]}
        | {c: [float(i) for i in range(n)] for c in cols},
    }


def test_frame_parses_naive_ist(monkeypatch):
    monkeypatch.setattr(om, "_get", lambda url, p: hourly_payload(om.VARS))
    df = om.archive(pd.Timestamp("2025-05-01").date(), pd.Timestamp("2025-05-01").date())
    assert list(df.columns) == ["time_ist"] + om.VARS
    assert df.time_ist.dt.tz is None
    assert df.time_ist.iloc[1] == pd.Timestamp("2025-05-01 01:00")


def test_previous_reshapes_leads_to_long(monkeypatch):
    seen = {}

    def fake_get(url, p):
        seen.update(p)
        cols = [f"{v}_previous_day{d}" for d in om.LEADS for v in om.VARS]
        pay = hourly_payload(cols)
        # make the two leads distinguishable
        for v in om.VARS:
            pay["hourly"][f"{v}_previous_day2"] = [100.0 + x for x in pay["hourly"][f"{v}_previous_day2"]]
        return pay

    monkeypatch.setattr(om, "_get", fake_get)
    d = pd.Timestamp("2025-05-01").date()
    df = om.previous(d, d, "ecmwf_ifs025")

    assert seen["models"] == "ecmwf_ifs025"
    assert set(df.columns) == {"time_ist", "model", "lead_days", *om.VARS}
    assert len(df) == 3 * len(om.LEADS)
    lead2 = df[df.lead_days == 2].shortwave_radiation.tolist()
    lead1 = df[df.lead_days == 1].shortwave_radiation.tolist()
    assert lead1 == [0.0, 1.0, 2.0] and lead2 == [100.0, 101.0, 102.0]


def test_get_raises_on_client_error(monkeypatch):
    class R:
        status_code = 400
        text = "bad variable"

    monkeypatch.setattr(om.requests, "get", lambda *a, **k: R())
    with pytest.raises(RuntimeError, match="400"):
        om._get("https://example.invalid", {})


def test_get_retries_then_succeeds(monkeypatch):
    calls = []

    class R:
        def __init__(self, code):
            self.status_code, self.text = code, ""

        def json(self):
            return {"ok": True}

    def fake(*a, **k):
        calls.append(1)
        return R(429 if len(calls) == 1 else 200)

    monkeypatch.setattr(om.requests, "get", fake)
    monkeypatch.setattr(om.time, "sleep", lambda s: None)
    assert om._get("https://example.invalid", {}) == {"ok": True}
    assert len(calls) == 2


# --- DuckDB catalogue ------------------------------------------------------------


def test_build_db_creates_views_only_for_present_sources(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DATA", tmp_path)
    df = pd.DataFrame({"time_ist": pd.date_range("2025-01-01", periods=2, freq="1h"), "shortwave_radiation": [0.0, 5.0]})
    store.write(df, tmp_path / "raw/openmeteo/archive/2025.parquet")
    made = store.build_db(tmp_path / "t.duckdb")
    assert made == ["archive_hourly"]

    import duckdb

    with duckdb.connect(str(tmp_path / "t.duckdb"), read_only=True) as con:
        assert con.execute("SELECT sum(shortwave_radiation) FROM archive_hourly").fetchone()[0] == 5.0


# --- daily job: once per day -------------------------------------------------


def test_daily_once_skips_after_pre_gate_run_or_one_late_run(tmp_path):
    import importlib.util
    from datetime import datetime

    spec = importlib.util.spec_from_file_location("daily", store.ROOT / "scripts" / "daily.py")
    daily = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(daily)

    early, late = datetime(2026, 10, 22, 4, 0), datetime(2026, 10, 22, 13, 0)
    assert not daily.done_today(early, tmp_path)
    assert not daily.done_today(late, tmp_path)  # nothing yet: late fallback runs
    (tmp_path / "2026-10-21T0850").mkdir()  # yesterday's run does not count
    assert not daily.done_today(late, tmp_path)
    (tmp_path / "2026-10-22T1215").mkdir()  # one late run is enough after the gate
    assert daily.done_today(late, tmp_path)
    (tmp_path / "2026-10-22T0900").mkdir()  # at the gate counts at any time
    assert daily.done_today(early, tmp_path)
