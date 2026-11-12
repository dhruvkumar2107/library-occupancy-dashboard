"""
Automated tests for the Campus Library Occupancy Dashboard.

Run from the project folder:   python -m pytest -v

The real CSV is backed up before the tests and restored afterwards, so running
the tests never changes your dataset.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

import generate_data  # noqa: E402
import library_core as lc  # noqa: E402
from streamlit.testing.v1 import AppTest  # noqa: E402


# --------------------------------------------------------------------------- #
# Fixtures / helpers
# --------------------------------------------------------------------------- #
@pytest.fixture(autouse=True)
def protect_csv(tmp_path):
    backup = tmp_path / "backup.csv"
    shutil.copy(lc.CSV_PATH, backup)
    yield
    shutil.copy(backup, lc.CSV_PATH)


def clean_df():
    return lc.clean(lc.load_raw())[0]


def run_app(page="overview", at=None):
    os.environ["DASHBOARD_START_PAGE"] = page
    at = at or AppTest.from_file(str(ROOT / "app.py"), default_timeout=90)
    at.run()
    assert not at.exception, [e.message for e in at.exception]
    return at


def kpi_values(at) -> dict:
    html = next(m.value for m in at.markdown if "class='kpi-grid'" in m.value)
    labels = re.findall(r"<div class='kpi-label'>(.*?)</div>", html)
    values = re.findall(r"<div class='kpi-value[^']*' title='[^']*'>(.*?)</div>", html)
    return dict(zip(labels, values))


def reset(at):
    next(b for b in at.button if b.label == "Reset filters").click().run()


def figure(at, idx=0) -> dict:
    return json.loads(at.get("plotly_chart")[idx].proto.spec)


def csv_lines() -> int:
    with open(lc.CSV_PATH, encoding="utf-8") as fh:
        return sum(1 for _ in fh)


# --------------------------------------------------------------------------- #
# 1. Dataset
# --------------------------------------------------------------------------- #
def test_dataset_has_required_columns_and_100_plus_records():
    raw = lc.load_raw()
    for col in ["Timestamp", "Building", "Floor", "Library_Zone", "Total_Seats",
                "Occupied_Seats", "Available_Seats", "Occupancy_Percentage", "Day", "Hour"]:
        assert col in raw.columns
    assert len(raw) >= 100
    assert (raw["Data_Source"] == "SIMULATED").all()
    assert set(raw["Library_Zone"].dropna()) == set(lc.ZONES)


def test_clean_data_is_internally_consistent():
    df = clean_df()
    assert (df["Available_Seats"] == df["Total_Seats"] - df["Occupied_Seats"]).all()
    assert np.allclose(df["Occupancy_Percentage"],
                       df["Occupied_Seats"] / df["Total_Seats"] * 100, atol=0.01)
    assert (df["Occupied_Seats"] <= df["Total_Seats"]).all()
    assert (df["Occupied_Seats"] >= 0).all()
    assert df["Timestamp"].notna().all()
    assert (df["Day"] == df["Timestamp"].dt.day_name()).all()
    assert (df["Hour"] == df["Timestamp"].dt.hour).all()


# --------------------------------------------------------------------------- #
# 2. Data quality: missing values, duplicates, invalid timestamps / readings
# --------------------------------------------------------------------------- #
def test_quality_report_detects_injected_issues():
    raw = lc.load_raw()
    df, rep = lc.clean(raw)
    assert rep.total_records == len(raw)
    assert rep.duplicate_records == 1
    assert rep.invalid_timestamps == 1
    assert rep.invalid_occupancy == 3          # missing, >capacity, negative
    assert rep.repaired_records == 1            # missing Total_Seats
    assert rep.missing_total == int(raw.isna().sum().sum())
    assert rep.clean_records == len(raw) - 5
    assert set(rep.issues["Action"]) == {"Excluded", "Repaired from seating layout"}


def _sample(n=3):
    return pd.DataFrame([generate_data.build_row(pd.Timestamp("2026-11-02 10:00") + pd.Timedelta(hours=i),
                                                 "Central Library", "Ground Floor", "Reading Hall",
                                                 150, 50 + i) for i in range(n)])


def test_missing_values_are_handled_not_silently_accepted():
    raw = _sample(4)
    raw.loc[0, "Occupied_Seats"] = np.nan          # unrecoverable -> excluded
    raw.loc[1, "Total_Seats"] = np.nan             # recoverable -> repaired to 150
    raw.loc[2, "Occupancy_Percentage"] = np.nan    # derived -> recalculated
    df, rep = lc.clean(raw)
    assert rep.missing_total == 3
    assert rep.invalid_occupancy == 1 and rep.repaired_records == 1
    assert rep.recalculated_fields >= 1
    assert len(df) == 3
    assert df["Total_Seats"].eq(150).all()
    assert df["Occupancy_Percentage"].notna().all()


def test_duplicate_detection():
    raw = pd.concat([_sample(3), _sample(3).iloc[[1]]], ignore_index=True)
    df, rep = lc.clean(raw)
    assert rep.duplicate_records == 1 and len(df) == 3


def test_invalid_timestamp_and_readings():
    raw = _sample(4)
    raw.loc[0, "Timestamp"] = "not a date"
    raw.loc[1, "Occupied_Seats"] = 999
    raw.loc[2, "Building"] = "Unknown Block"
    df, rep = lc.clean(raw)
    assert rep.invalid_timestamps == 1 and rep.invalid_occupancy == 1 and rep.unknown_location == 1
    assert len(df) == 1


# --------------------------------------------------------------------------- #
# 3. KPI calculations (checked against an independent manual calculation)
# --------------------------------------------------------------------------- #
def test_kpis_match_manual_calculation():
    df = clean_df()
    k = lc.compute_kpis(df)
    latest = {}
    for _, r in df.iterrows():                      # pure-python reference
        key = (r.Building, r.Floor, r.Library_Zone)
        if key not in latest or r.Timestamp >= latest[key].Timestamp:
            latest[key] = r
    total = sum(r.Total_Seats for r in latest.values())
    occ = sum(r.Occupied_Seats for r in latest.values())
    assert k["total_seats"] == total == 468
    assert k["current_occupied"] == occ
    assert k["available_seats"] == total - occ
    assert k["overall_occupancy_pct"] == pytest.approx(
        df.Occupied_Seats.sum() / df.Total_Seats.sum() * 100)
    hourly = df.groupby(df.Timestamp.dt.floor("h")).apply(
        lambda g: g.Occupied_Seats.sum() / g.Total_Seats.sum() * 100)
    assert k["peak_occupancy_pct"] == pytest.approx(hourly.max())
    zone = df.groupby("Library_Zone").apply(lambda g: g.Occupied_Seats.sum() / g.Total_Seats.sum())
    assert k["busiest_zone"] == zone.idxmax()


def test_dashboard_kpi_cards_show_computed_values():
    at = run_app()
    k = lc.compute_kpis(clean_df())
    v = kpi_values(at)
    assert v["Total Library Seats"] == f"{k['total_seats']:,}"
    assert v["Currently Occupied"] == f"{k['current_occupied']:,}"
    assert v["Available Seats"] == f"{k['available_seats']:,}"
    assert v["Overall Occupancy"] == f"{k['overall_occupancy_pct']:.1f}%"
    assert v["Peak Occupancy"] == f"{k['peak_occupancy_pct']:.1f}%"
    assert v["Busiest Library Zone"] == k["busiest_zone"]


# --------------------------------------------------------------------------- #
# 4. Filters
# --------------------------------------------------------------------------- #
def test_every_filter_changes_kpis_and_reset_restores():
    at = run_app()
    base = kpi_values(at)

    at.multiselect(key="f_build").set_value(["Engineering Library"]).run()
    v = kpi_values(at)
    assert v["Total Library Seats"] == "178"                  # 48 + 90 + 40
    reset(at)                              # Reset filters
    assert kpi_values(at) == base

    at.multiselect(key="f_floor").set_value(["Second Floor"]).run()
    assert kpi_values(at)["Total Library Seats"] == "80"
    assert kpi_values(at)["Busiest Library Zone"] == "Silent Study Area"

    at.multiselect(key="f_floor").set_value(["Ground Floor", "First Floor", "Second Floor"]).run()
    at.multiselect(key="f_zone").set_value(["Group Study Area"]).run()
    assert kpi_values(at)["Total Library Seats"] == "48"

    at.multiselect(key="f_zone").set_value(lc.ZONES).run()
    at.slider(key="f_hours").set_value((8, 10)).run()
    v = kpi_values(at)
    assert float(v["Overall Occupancy"].rstrip("%")) < float(base["Overall Occupancy"].rstrip("%"))

    df = clean_df()
    d0 = df["Date"].min()
    at.slider(key="f_hours").set_value((8, 21)).run()
    at.date_input(key="f_dates").set_value((d0, d0)).run()
    expected = lc.compute_kpis(lc.apply_filters(df, (d0, d0)))
    assert kpi_values(at)["Peak Occupancy"] == f"{expected['peak_occupancy_pct']:.1f}%"

    reset(at)
    assert kpi_values(at) == base


def test_empty_filter_selection_shows_warning():
    at = run_app()
    at.multiselect(key="f_zone").set_value([]).run()
    assert any("No records match" in w.value for w in at.warning)


# --------------------------------------------------------------------------- #
# 5. Simulated real-time updates
# --------------------------------------------------------------------------- #
def _submit_manual(at, loc, occ, date, time):
    at.selectbox(key="m_loc").set_value(loc)
    at.number_input(key="m_occ").set_value(occ)
    at.date_input(key="m_date").set_value(date)
    at.time_input(key="m_time").set_value(time)
    next(b for b in at.button if b.label == "Submit record").click().run()


def test_manual_record_updates_csv_kpis_and_charts():
    at = run_app("live")
    lines_before = csv_lines()
    before = lc.compute_kpis(clean_df())
    new_day = clean_df()["Date"].max() + dt.timedelta(days=1)
    _submit_manual(at, "Central Library · Ground Floor · Reading Hall", 5, new_day, dt.time(9, 0))
    assert not at.exception
    assert any("Manual record saved" in s.value for s in at.success)
    assert csv_lines() == lines_before + 1                       # CSV changed
    last = lc.load_raw().iloc[-1]
    assert last["Timestamp"] == f"{new_day} 09:00:00" and last["Occupied_Seats"] == 5
    assert last["Available_Seats"] == 145 and last["Occupancy_Percentage"] == pytest.approx(3.33)
    after = lc.compute_kpis(clean_df())
    assert after["records"] == before["records"] + 1
    assert after["snapshot_time"] == pd.Timestamp(f"{new_day} 09:00")
    # filter date range extended automatically, and the trend chart now ends at the new record
    trend = figure(at, 0)
    xs = [x for tr in trend["data"] for x in tr["x"]]
    assert max(xs).startswith(f"{new_day}T09:00")
    # the overview KPIs reflect the new data
    os.environ["DASHBOARD_START_PAGE"] = "overview"
    at2 = run_app("overview")
    assert kpi_values(at2)["Currently Occupied"] == f"{after['current_occupied']:,}"


def test_manual_record_rejected_when_exceeding_capacity_or_duplicate():
    at = run_app("live")
    lines = csv_lines()
    _submit_manual(at, "Engineering Library · Ground Floor · Group Study Area", 60,
                   clean_df()["Date"].max(), dt.time(10, 0))
    assert any("cannot exceed" in e.value for e in at.error)
    first = clean_df().iloc[0]
    _submit_manual(at, first["Location"], 10, first["Date"], first["Timestamp"].time())
    assert any("duplicate" in e.value for e in at.error)
    _submit_manual(at, first["Location"], 10, first["Date"], dt.time(23, 0))
    assert any("opening hours" in e.value for e in at.error)
    assert csv_lines() == lines                                  # nothing written


def test_random_record_button_adds_realistic_rows():
    at = run_app("live")
    lines = csv_lines()
    prev_max = clean_df()["Timestamp"].max()
    at.slider(key="r_count").set_value(3)
    next(b for b in at.button if b.label == "Add random record").click().run()
    assert not at.exception
    assert csv_lines() == lines + 3
    df, rep = lc.clean(lc.load_raw())
    new = df[df["Timestamp"] > prev_max]
    assert len(new) == 3
    assert (new["Occupied_Seats"] <= new["Total_Seats"]).all()
    assert rep.clean_records == rep.total_records - 5         # new rows are all valid
    assert len(at.dataframe) >= 2                               # latest record + raw tail shown


def test_restore_dataset():
    at = run_app("live")
    next(b for b in at.button if b.label == "Add random record").click().run()
    at.checkbox(key="restore_ok").check().run()
    next(b for b in at.button if b.label == "Restore original dataset").click().run()
    assert len(lc.load_raw()) == len(generate_data.generate())


# --------------------------------------------------------------------------- #
# 6. Insights are data-driven
# --------------------------------------------------------------------------- #
def test_insights_follow_the_data():
    df = clean_df()
    findings, recs = lc.generate_insights(df)
    k = lc.compute_kpis(df)
    assert any(k["busiest_zone"] in f for f in findings)
    only_group = lc.apply_filters(df, zones=["Group Study Area"])
    f2, _ = lc.generate_insights(only_group)
    assert f2 != findings and "Group Study Area" in f2[1]
    assert recs


# --------------------------------------------------------------------------- #
# 7. All pages load; all deliverables exist
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("page", ["overview", "occupancy", "zones", "peak-hours", "live",
                                  "data-quality", "about"])
def test_every_page_renders(page):
    run_app(page)


def test_deliverables_exist():
    for p in ["app.py", "data/library_occupancy.csv", "requirements.txt", "README.md",
              "presentation_notes.md", "screenshots/dashboard_screenshot.png"]:
        assert (ROOT / p).exists(), p
