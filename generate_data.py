"""
generate_data.py
----------------
Generates the SIMULATED campus library occupancy dataset used by the dashboard.

*** THIS IS SIMULATED DATA - it is NOT collected from real campus sensors. ***

Run:  python generate_data.py
Output: data/library_occupancy.csv

The generator models realistic behaviour:
  * hourly readings while the library is open (08:00 - 21:00)
  * a morning ramp-up, an afternoon peak and an evening decline
  * lower demand on weekends, higher demand in the second (exam) week
  * the final day stops at 15:00 to represent "today, so far"
  * zone-specific demand (Reading Hall and Silent Study fill up most)

To demonstrate the data-quality module, a handful of deliberately flawed rows
(missing values, a duplicate, a bad timestamp, an impossible occupancy reading)
are appended at the end. The dashboard detects, reports and excludes/repairs them.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
START_DATE = "2026-10-29"   # a Thursday
N_DAYS = 14
OPEN_HOUR, CLOSE_HOUR = 8, 21   # last reading taken at 21:00
LAST_DAY_END_HOUR = 15          # final day is "today": readings so far up to 15:00

# Physical seating layout of the (fictional) campus libraries.
# (Building, Floor, Library_Zone, Total_Seats, demand multiplier)
LOCATIONS = [
    ("Central Library",     "Ground Floor", "Reading Hall",      150, 1.00),
    ("Central Library",     "First Floor",  "Digital Library",    60, 0.85),
    ("Central Library",     "Second Floor", "Silent Study Area",  80, 1.05),
    ("Engineering Library", "Ground Floor", "Group Study Area",   48, 0.70),
    ("Engineering Library", "First Floor",  "Reading Hall",       90, 0.92),
    ("Engineering Library", "First Floor",  "Digital Library",    40, 0.80),
]

COLUMNS = [
    "Timestamp", "Building", "Floor", "Library_Zone", "Total_Seats",
    "Occupied_Seats", "Available_Seats", "Occupancy_Percentage", "Day", "Hour",
    "Data_Source",
]

# Base hourly demand curve (fraction of seats in use) for a typical weekday.
HOURLY_CURVE = {
    8: 0.22, 9: 0.38, 10: 0.55, 11: 0.66, 12: 0.62, 13: 0.70, 14: 0.82,
    15: 0.88, 16: 0.84, 17: 0.72, 18: 0.60, 19: 0.52, 20: 0.40, 21: 0.25,
}


def expected_rate(hour: int, weekday: int, day_index: int, demand: float) -> float:
    """Expected occupancy fraction for a location at a given hour/day."""
    rate = HOURLY_CURVE[hour] * demand
    if weekday >= 5:            # Saturday / Sunday
        rate *= 0.55
    if day_index >= 7:          # second week = exam preparation week
        rate *= 1.10
    return rate


def simulate_occupied(total: int, rate: float, rng: np.random.Generator) -> int:
    noisy = rate + rng.normal(0, 0.06)
    noisy = min(max(noisy, 0.02), 1.0)
    return int(min(total, max(0, round(total * noisy))))   # never exceeds capacity


def build_row(ts: pd.Timestamp, building, floor, zone, total, occupied) -> dict:
    return {
        "Timestamp": ts.strftime("%Y-%m-%d %H:%M:%S"),
        "Building": building,
        "Floor": floor,
        "Library_Zone": zone,
        "Total_Seats": total,
        "Occupied_Seats": occupied,
        "Available_Seats": total - occupied,
        "Occupancy_Percentage": round(occupied / total * 100, 2),
        "Day": ts.day_name(),
        "Hour": ts.hour,
        "Data_Source": "SIMULATED",
    }


def generate(seed: int = SEED) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    start = pd.Timestamp(START_DATE)
    for d in range(N_DAYS):
        day = start + pd.Timedelta(days=d)
        last_hour = LAST_DAY_END_HOUR if d == N_DAYS - 1 else CLOSE_HOUR
        for hour in range(OPEN_HOUR, last_hour + 1):
            ts = day + pd.Timedelta(hours=hour)
            for building, floor, zone, total, demand in LOCATIONS:
                rate = expected_rate(hour, ts.weekday(), d, demand)
                occ = simulate_occupied(total, rate, rng)
                rows.append(build_row(ts, building, floor, zone, total, occ))
    df = pd.DataFrame(rows, columns=COLUMNS)

    # ---- Deliberately flawed records (to demonstrate data-quality handling) ----
    flawed = [
        # 1. Exact duplicate of an existing reading (sensor sent twice)
        df.iloc[100].to_dict(),
        # 2. Missing occupied-seat reading (sensor dropout)
        {**df.iloc[0].to_dict(), "Timestamp": "2026-11-01 08:30:00",
         "Occupied_Seats": np.nan, "Available_Seats": np.nan,
         "Occupancy_Percentage": np.nan, "Day": "Sunday", "Hour": 8},
        # 3. Unparseable timestamp
        {**df.iloc[5].to_dict(), "Timestamp": "2026-13-45 25:00:00"},
        # 4. Occupied seats exceed capacity (faulty counter)
        {**df.iloc[20].to_dict(), "Timestamp": "2026-11-01 09:30:00",
         "Occupied_Seats": 175, "Available_Seats": -25,
         "Occupancy_Percentage": 116.67, "Day": "Sunday", "Hour": 9},
        # 5. Negative reading
        {**df.iloc[31].to_dict(), "Timestamp": "2026-11-01 10:30:00",
         "Occupied_Seats": -4, "Available_Seats": 52,
         "Occupancy_Percentage": -8.33, "Day": "Sunday", "Hour": 10},
        # 6. Missing Total_Seats (repairable from the known seating layout)
        {**df.iloc[40].to_dict(), "Timestamp": "2026-11-01 11:30:00",
         "Total_Seats": np.nan, "Day": "Sunday", "Hour": 11},
    ]
    df = pd.concat([df, pd.DataFrame(flawed, columns=COLUMNS)], ignore_index=True)
    return df


def main() -> None:
    out = Path(__file__).parent / "data" / "library_occupancy.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    df = generate()
    df.to_csv(out, index=False)
    print(f"[SIMULATED DATA] wrote {len(df)} records to {out}")


if __name__ == "__main__":
    main()
