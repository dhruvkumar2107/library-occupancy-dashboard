"""
library_core.py
---------------
Pure data logic for the Campus Library Occupancy Dashboard (no Streamlit code).

  * load + validate + clean the raw CSV
  * apply dashboard filters
  * compute KPIs
  * aggregate data for charts
  * generate data-driven insights and recommendations
  * append new (simulated) records to the CSV

All data handled here is SIMULATED - see generate_data.py.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from generate_data import (CLOSE_HOUR, COLUMNS, LOCATIONS, OPEN_HOUR,
                           build_row, expected_rate, simulate_occupied)

BASE_DIR = Path(__file__).parent
CSV_PATH = BASE_DIR / "data" / "library_occupancy.csv"
TS_FORMAT = "%Y-%m-%d %H:%M:%S"
LOC_KEYS = ["Building", "Floor", "Library_Zone"]
DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
             "Saturday", "Sunday"]
ZONES = ["Reading Hall", "Digital Library", "Group Study Area", "Silent Study Area"]

# Known seating layout: (Building, Floor, Zone) -> capacity. Used to validate
# readings and to repair a missing Total_Seats value.
CAPACITY = {(b, f, z): seats for b, f, z, seats, _ in LOCATIONS}
DEMAND = {(b, f, z): dem for b, f, z, _, dem in LOCATIONS}


# --------------------------------------------------------------------------- #
# Loading and cleaning
# --------------------------------------------------------------------------- #
@dataclass
class QualityReport:
    total_records: int = 0
    clean_records: int = 0
    missing_by_column: dict = field(default_factory=dict)
    missing_total: int = 0
    duplicate_records: int = 0
    invalid_timestamps: int = 0
    invalid_occupancy: int = 0
    unknown_location: int = 0
    repaired_records: int = 0
    recalculated_fields: int = 0
    issues: pd.DataFrame = field(default_factory=pd.DataFrame)


def load_raw(path: Path = CSV_PATH) -> pd.DataFrame:
    """Read the CSV exactly as stored (no cleaning)."""
    return pd.read_csv(path)


def clean(raw: pd.DataFrame) -> tuple[pd.DataFrame, QualityReport]:
    """Validate and clean raw records.

    Rules (nothing invalid is silently accepted):
      1. Timestamp missing / unparseable            -> EXCLUDED
      2. Unknown Building/Floor/Zone combination    -> EXCLUDED
      3. Total_Seats missing                        -> REPAIRED from the seating layout
      4. Occupied_Seats missing                     -> EXCLUDED (a reading cannot be guessed)
      5. Occupied_Seats < 0 or > Total_Seats        -> EXCLUDED
      6. Duplicate (same time + location)           -> later copy EXCLUDED
      7. Available_Seats, Occupancy_Percentage, Day, Hour are always
         RECALCULATED from Timestamp/Total/Occupied (stored values not trusted).
    """
    rep = QualityReport(total_records=len(raw))
    df = raw.copy()
    for col in COLUMNS:
        if col not in df.columns:
            df[col] = np.nan
    df["CSV_Row"] = df.index + 2          # line number in the CSV (header = 1)

    rep.missing_by_column = {c: int(raw[c].isna().sum()) if c in raw else len(raw)
                             for c in COLUMNS}
    rep.missing_total = int(sum(rep.missing_by_column.values()))

    issues: list[dict] = []

    def log(rows: pd.DataFrame, reason: str, action: str) -> None:
        for _, r in rows.iterrows():
            issues.append({"CSV_Row": r["CSV_Row"], "Timestamp": r["Timestamp_raw"],
                           "Building": r["Building"], "Library_Zone": r["Library_Zone"],
                           "Occupied_Seats": r["Occupied_Seats"],
                           "Issue": reason, "Action": action})

    df["Timestamp_raw"] = df["Timestamp"].astype("string")
    df["Timestamp"] = pd.to_datetime(df["Timestamp"], format=TS_FORMAT, errors="coerce")
    df["Total_Seats"] = pd.to_numeric(df["Total_Seats"], errors="coerce")
    df["Occupied_Seats"] = pd.to_numeric(df["Occupied_Seats"], errors="coerce")

    # 1. invalid timestamps
    bad_ts = df["Timestamp"].isna()
    rep.invalid_timestamps = int(bad_ts.sum())
    log(df[bad_ts], "Missing or invalid timestamp", "Excluded")
    df = df[~bad_ts]

    # 2. unknown location
    known = df.apply(lambda r: (r["Building"], r["Floor"], r["Library_Zone"]) in CAPACITY,
                     axis=1) if len(df) else pd.Series(dtype=bool)
    rep.unknown_location = int((~known).sum())
    log(df[~known], "Unknown building/floor/zone", "Excluded")
    df = df[known].copy()

    # 3. repair missing capacity from the known layout
    cap = df.apply(lambda r: CAPACITY[(r["Building"], r["Floor"], r["Library_Zone"])],
                   axis=1) if len(df) else pd.Series(dtype=float)
    miss_total = df["Total_Seats"].isna()
    rep.repaired_records = int(miss_total.sum())
    log(df[miss_total], "Missing Total_Seats", "Repaired from seating layout")
    df.loc[miss_total, "Total_Seats"] = cap[miss_total]

    # 4./5. invalid occupancy readings
    occ = df["Occupied_Seats"]
    miss_occ = occ.isna()
    negative = occ < 0
    over = occ > df["Total_Seats"]
    non_int = occ.notna() & (occ % 1 != 0)
    log(df[miss_occ], "Missing Occupied_Seats reading", "Excluded")
    log(df[negative], "Negative occupied seats", "Excluded")
    log(df[over], "Occupied seats exceed total seats", "Excluded")
    log(df[non_int & ~negative & ~over], "Non-integer seat count", "Excluded")
    bad_occ = miss_occ | negative | over | non_int
    rep.invalid_occupancy = int(bad_occ.sum())
    df = df[~bad_occ].copy()

    # 6. duplicates on (time, location)
    dup = df.duplicated(subset=["Timestamp"] + LOC_KEYS, keep="first")
    rep.duplicate_records = int(dup.sum())
    log(df[dup], "Duplicate reading (same time & location)", "Excluded")
    df = df[~dup].copy()

    # 7. recalculate derived fields; count rows whose stored values disagreed
    df["Total_Seats"] = df["Total_Seats"].astype(int)
    df["Occupied_Seats"] = df["Occupied_Seats"].astype(int)
    avail = df["Total_Seats"] - df["Occupied_Seats"]
    pct = (df["Occupied_Seats"] / df["Total_Seats"] * 100).round(2)
    day = df["Timestamp"].dt.day_name()
    hour = df["Timestamp"].dt.hour
    stored_pct = pd.to_numeric(df["Occupancy_Percentage"], errors="coerce")
    stored_av = pd.to_numeric(df["Available_Seats"], errors="coerce")
    stored_hr = pd.to_numeric(df["Hour"], errors="coerce")
    mismatch = ((stored_av != avail)                                   # NaN counts as mismatch
                | ~pd.Series(np.isclose(stored_pct, pct, atol=0.01), index=df.index)
                | (df["Day"] != day) | (stored_hr != hour))
    rep.recalculated_fields = int(mismatch.sum())
    log(df[mismatch], "Derived fields missing/inconsistent", "Recalculated")
    df["Available_Seats"], df["Occupancy_Percentage"] = avail, pct
    df["Day"], df["Hour"] = day, hour

    df = df.drop(columns=["Timestamp_raw"]).sort_values("Timestamp").reset_index(drop=True)
    df["Date"] = df["Timestamp"].dt.date
    df["Day_Type"] = np.where(df["Timestamp"].dt.weekday >= 5, "Weekend", "Weekday")
    df["Location"] = df["Building"] + " · " + df["Floor"] + " · " + df["Library_Zone"]

    rep.clean_records = len(df)
    rep.issues = pd.DataFrame(issues, columns=["CSV_Row", "Timestamp", "Building",
                                               "Library_Zone", "Occupied_Seats",
                                               "Issue", "Action"])
    return df, rep


# --------------------------------------------------------------------------- #
# Filtering
# --------------------------------------------------------------------------- #
def apply_filters(df, date_range=None, buildings=None, floors=None, zones=None,
                  hour_range=None) -> pd.DataFrame:
    m = pd.Series(True, index=df.index)
    if date_range:
        start, end = date_range
        m &= (df["Date"] >= start) & (df["Date"] <= end)
    if buildings is not None:
        m &= df["Building"].isin(buildings)
    if floors is not None:
        m &= df["Floor"].isin(floors)
    if zones is not None:
        m &= df["Library_Zone"].isin(zones)
    if hour_range:
        m &= df["Hour"].between(hour_range[0], hour_range[1])
    return df[m]


# --------------------------------------------------------------------------- #
# Aggregations
# --------------------------------------------------------------------------- #
def hourly_snapshots(df: pd.DataFrame, by: str | None = None) -> pd.DataFrame:
    """Library-wide (or per `by`) occupancy for each clock-hour slot.

    If one location has several readings inside the same hour (e.g. a manual
    record), only its latest reading is used so seats are never double counted.
    """
    if df.empty:
        return pd.DataFrame(columns=["Slot", "Occupied_Seats", "Total_Seats",
                                     "Occupancy_Percentage"])
    d = df.assign(Slot=df["Timestamp"].dt.floor("h")).sort_values("Timestamp")
    d = d.drop_duplicates(subset=["Slot"] + LOC_KEYS, keep="last")
    keys = ["Slot"] + ([by] if by else [])
    g = d.groupby(keys, as_index=False)[["Occupied_Seats", "Total_Seats"]].sum()
    g["Occupancy_Percentage"] = g["Occupied_Seats"] / g["Total_Seats"] * 100
    g["Hour"] = g["Slot"].dt.hour
    g["Day"] = g["Slot"].dt.day_name()
    g["Date"] = g["Slot"].dt.date
    return g


def ratio_by(df: pd.DataFrame, key) -> pd.DataFrame:
    """Seat-weighted occupancy % (sum occupied / sum capacity) per group."""
    g = df.groupby(key, as_index=False).agg(
        Occupied_Seats=("Occupied_Seats", "sum"), Total_Seats=("Total_Seats", "sum"),
        Readings=("Occupied_Seats", "size"),
        Avg_Available=("Available_Seats", "mean"))
    g["Occupancy_Percentage"] = g["Occupied_Seats"] / g["Total_Seats"] * 100
    return g


def latest_snapshot(df: pd.DataFrame) -> pd.DataFrame:
    """Most recent reading for each physical location."""
    return df.sort_values("Timestamp").groupby(LOC_KEYS, as_index=False).tail(1)


# --------------------------------------------------------------------------- #
# KPIs
# --------------------------------------------------------------------------- #
def compute_kpis(df: pd.DataFrame) -> dict | None:
    if df.empty:
        return None
    latest = latest_snapshot(df)
    total = int(latest["Total_Seats"].sum())
    occupied = int(latest["Occupied_Seats"].sum())
    snaps = hourly_snapshots(df)
    peak = snaps.loc[snaps["Occupancy_Percentage"].idxmax()]
    zones = ratio_by(df, "Library_Zone")
    busiest = zones.loc[zones["Occupancy_Percentage"].idxmax()]
    return {
        "total_seats": total,
        "current_occupied": occupied,
        "available_seats": total - occupied,
        "current_occupancy_pct": occupied / total * 100 if total else 0.0,
        "overall_occupancy_pct": df["Occupied_Seats"].sum() / df["Total_Seats"].sum() * 100,
        "peak_occupancy_pct": float(peak["Occupancy_Percentage"]),
        "peak_time": peak["Slot"],
        "busiest_zone": busiest["Library_Zone"],
        "busiest_zone_pct": float(busiest["Occupancy_Percentage"]),
        "snapshot_time": latest["Timestamp"].max(),
        "locations": len(latest),
        "records": len(df),
    }


# --------------------------------------------------------------------------- #
# Insights
# --------------------------------------------------------------------------- #
def _period(hour: int) -> str:
    if hour < 12:
        return "morning"
    if hour < 14:
        return "midday"
    if hour < 18:
        return "afternoon"
    return "evening"


def _hours_label(hours: list[int]) -> str:
    """[14, 15, 16, 19] -> '14:00–16:59, 19:00–19:59'"""
    if not hours:
        return ""
    hours = sorted(hours)
    runs, start, prev = [], hours[0], hours[0]
    for h in hours[1:]:
        if h != prev + 1:
            runs.append((start, prev))
            start = h
        prev = h
    runs.append((start, prev))
    return ", ".join(f"{a:02d}:00–{b:02d}:59" for a, b in runs)


def generate_insights(df: pd.DataFrame) -> tuple[list[str], list[str]]:
    """Return (findings, recommendations), all computed from `df`."""
    if df.empty:
        return [], []
    findings, recs = [], []
    snaps = hourly_snapshots(df)

    # 1. Peak hour / period
    by_hour = snaps.groupby("Hour")["Occupancy_Percentage"].mean()
    peak_h = int(by_hour.idxmax())
    period = snaps.assign(P=snaps["Hour"].map(_period)).groupby("P")[
        "Occupancy_Percentage"].mean()
    findings.append(
        f"Library-wide occupancy peaks at **{peak_h:02d}:00** "
        f"(average **{by_hour.max():.1f}%**). The **{_period(peak_h)}** is the busiest "
        f"period on average ({period.get(_period(peak_h), float('nan')):.1f}%), while the "
        f"quietest hour is {int(by_hour.idxmin()):02d}:00 ({by_hour.min():.1f}%).")

    # 2. Zone demand
    zones = ratio_by(df, "Library_Zone").sort_values("Occupancy_Percentage", ascending=False)
    top, low = zones.iloc[0], zones.iloc[-1]
    if len(zones) > 1:
        findings.append(
            f"**{top['Library_Zone']}** has the highest demand "
            f"(**{top['Occupancy_Percentage']:.1f}%** average occupancy), "
            f"{top['Occupancy_Percentage'] - low['Occupancy_Percentage']:.1f} percentage points "
            f"above **{low['Library_Zone']}** ({low['Occupancy_Percentage']:.1f}%).")
        findings.append(
            f"**{low['Library_Zone']}** has comparatively the most spare capacity: "
            f"{100 - low['Occupancy_Percentage']:.1f}% of its seats are free on average "
            f"(about {low['Avg_Available']:.0f} seats per location).")
    else:
        findings.append(f"Only **{top['Library_Zone']}** is selected; its average "
                        f"occupancy is {top['Occupancy_Percentage']:.1f}%.")

    # 3. Day-of-week / weekend
    days = ratio_by(df, "Day")
    busiest_day = days.loc[days["Occupancy_Percentage"].idxmax()]
    dt = ratio_by(df, "Day_Type").set_index("Day_Type")["Occupancy_Percentage"]
    msg = (f"**{busiest_day['Day']}** is the busiest day of the week "
           f"({busiest_day['Occupancy_Percentage']:.1f}%).")
    if {"Weekday", "Weekend"} <= set(dt.index):
        msg += (f" Weekday occupancy ({dt['Weekday']:.1f}%) is "
                f"{dt['Weekday'] / dt['Weekend']:.1f}× the weekend level ({dt['Weekend']:.1f}%).")
    findings.append(msg)

    # 4. Saturation (readings at >= 90%)
    sat = df.assign(S=df["Occupancy_Percentage"] >= 90).groupby("Library_Zone")["S"].mean() * 100
    if sat.max() > 0:
        findings.append(
            f"**{sat.idxmax()}** is near-full (≥ 90% occupied) in "
            f"**{sat.max():.1f}%** of its hourly readings — students are likely being turned away.")

    # 5. Trend between halves of the period
    dates = sorted(df["Date"].unique())
    if len(dates) >= 4:
        mid = dates[len(dates) // 2]
        first = df[df["Date"] < mid]
        second = df[df["Date"] >= mid]
        a = first["Occupied_Seats"].sum() / first["Total_Seats"].sum() * 100
        b = second["Occupied_Seats"].sum() / second["Total_Seats"].sum() * 100
        direction = "rose" if b > a else "fell"
        findings.append(f"Average occupancy **{direction}** from {a:.1f}% in the first half "
                        f"of the selected period to {b:.1f}% in the second half "
                        f"({b - a:+.1f} pp).")
        if b - a >= 5:
            recs.append("Demand is rising over time (consistent with an approaching exam period). "
                        "Plan **extended opening hours** and temporary overflow seating for "
                        "exam weeks.")

    # Recommendations driven by thresholds
    zone_hour = hourly_snapshots(df, by="Library_Zone").groupby(
        ["Library_Zone", "Hour"])["Occupancy_Percentage"].mean().reset_index()
    for zone in zones["Library_Zone"]:
        hot = zone_hour[(zone_hour["Library_Zone"] == zone)
                        & (zone_hour["Occupancy_Percentage"] >= 80)]["Hour"].tolist()
        if hot:
            recs.append(f"**{zone}** averages ≥ 80% occupancy during "
                        f"**{_hours_label(hot)}**. Open overflow space (e.g. vacant "
                        f"classrooms) or introduce seat-booking during these hours.")
    if len(zones) > 1 and top["Occupancy_Percentage"] - low["Occupancy_Percentage"] >= 15:
        recs.append(f"**Redistribute seating**: move some furniture or re-purpose part of "
                    f"**{low['Library_Zone']}** to support **{top['Library_Zone']}** during "
                    f"peak periods.")
    quiet = by_hour[by_hour < 35].index.tolist()
    if quiet:
        recs.append(f"Library-wide occupancy is below 35% during **{_hours_label(quiet)}**. "
                    f"Schedule cleaning, maintenance and staff breaks in these windows.")
    if {"Weekday", "Weekend"} <= set(dt.index) and dt["Weekend"] < 0.7 * dt["Weekday"]:
        recs.append("Weekend demand is much lower — consider **reduced weekend staffing** or "
                    "closing lower-demand floors on weekends to save energy.")
    if not recs:
        recs.append("Occupancy is balanced across zones and hours for the current selection; "
                    "no capacity changes are required.")
    recs.append("Show **live seat availability** on screens at the library entrance and in "
                "the student app so students can choose a less crowded zone.")
    return findings, recs


# --------------------------------------------------------------------------- #
# Writing new records (simulated real-time updates)
# --------------------------------------------------------------------------- #
class RecordError(ValueError):
    pass


def make_record(ts: pd.Timestamp, building: str, floor: str, zone: str,
                occupied: int) -> dict:
    """Validate and build a new record. Raises RecordError if invalid."""
    key = (building, floor, zone)
    if key not in CAPACITY:
        raise RecordError(f"Unknown location: {building} / {floor} / {zone}")
    total = CAPACITY[key]
    if pd.isna(ts):
        raise RecordError("Timestamp is missing or invalid.")
    if not (OPEN_HOUR <= ts.hour <= CLOSE_HOUR):
        raise RecordError(f"Timestamp must be within opening hours "
                          f"({OPEN_HOUR:02d}:00–{CLOSE_HOUR:02d}:59).")
    if occupied is None or int(occupied) != occupied:
        raise RecordError("Occupied seats must be a whole number.")
    if occupied < 0:
        raise RecordError("Occupied seats cannot be negative.")
    if occupied > total:
        raise RecordError(f"Occupied seats ({occupied}) cannot exceed the {total} "
                          f"seats available in this zone.")
    return build_row(pd.Timestamp(ts).floor("s"), building, floor, zone, total, int(occupied))


def is_duplicate(df_clean: pd.DataFrame, record: dict) -> bool:
    ts = pd.Timestamp(record["Timestamp"])
    m = ((df_clean["Timestamp"] == ts) & (df_clean["Building"] == record["Building"])
         & (df_clean["Floor"] == record["Floor"])
         & (df_clean["Library_Zone"] == record["Library_Zone"]))
    return bool(m.any())


def append_record(record: dict, path: Path = CSV_PATH) -> None:
    """Append one row to the CSV (keeps the original column order)."""
    with open(path, "rb+") as fh:          # make sure the file ends with a newline
        fh.seek(0, 2)
        if fh.tell() > 0:
            fh.seek(-1, 2)
            if fh.read(1) not in (b"\n", b"\r"):
                fh.write(b"\n")
    with open(path, "a", newline="", encoding="utf-8") as fh:
        csv.DictWriter(fh, fieldnames=COLUMNS).writerow({c: record[c] for c in COLUMNS})


def random_record(df_clean: pd.DataFrame, rng: np.random.Generator | None = None) -> dict:
    """A realistic next reading: the next hourly slot after the latest record,
    for a random location, using the same demand model as the generator."""
    rng = rng or np.random.default_rng()
    last = df_clean["Timestamp"].max() if not df_clean.empty else pd.Timestamp.now().floor("h")
    ts = last.floor("h") + pd.Timedelta(hours=1)
    if ts.hour > CLOSE_HOUR:
        ts = ts.normalize() + pd.Timedelta(days=1, hours=OPEN_HOUR)
    elif ts.hour < OPEN_HOUR:
        ts = ts.normalize() + pd.Timedelta(hours=OPEN_HOUR)
    building, floor, zone, total, demand = LOCATIONS[rng.integers(len(LOCATIONS))]
    rate = expected_rate(ts.hour, ts.weekday(), 7, demand)
    occupied = simulate_occupied(total, rate, rng)
    return make_record(ts, building, floor, zone, occupied)
