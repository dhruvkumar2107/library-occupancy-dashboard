# Presentation Notes — Campus Library Occupancy Monitoring Dashboard

**Total time:** about 12–15 minutes (≈ 4 minutes per student) plus Q&A.
**Before class:** run `python generate_data.py` (fresh dataset) and then `streamlit run app.py`.
Keep the dashboard open on the **Overview** page with all filters at their defaults.

> Numbers below are what the dashboard shows for the original dataset with no filters. They are
> calculated live, so they will change after records are added — that is expected.

---

## Student 1 — Introduction, problem, dataset and data cleaning (≈ 4 min)

**Pages to show:** Project Information → Data Quality

### Why we chose this theme
"We chose library occupancy because every student has experienced it: you walk to the library
during exams and the Reading Hall is full, while another floor has empty seats. It is a real
campus problem, it produces time-based numeric data that is good for visualisation, and the
decisions it supports — staffing, seating, opening hours — are easy to explain."

### The problem we are solving
"Administrators do not know **when** and **where** demand peaks. Without data, staffing,
furniture and opening hours are planned by guesswork. Our dashboard shows current
availability, historical patterns and recommendations."

### Who will use it
- **Library administrators** — daily monitoring and staffing.
- **College management** — capacity planning and budgeting.
- **Students** — finding a free seat.
- **Facility managers** — scheduling cleaning and maintenance in quiet hours.

### The dataset (say clearly: SIMULATED)
"The data is **simulated** — we generated it with a Python script because we have no access to
real sensors. Every page shows a 'SIMULATED DATA' badge."
- 2 libraries, 6 zone locations, 4 zone types, **468 seats** in total.
- Hourly readings from 08:00 to 21:00 for 14 days → **1,140 readings**, plus 6 deliberately
  flawed rows → **1,146 rows**.
- 10 required columns: Timestamp, Building, Floor, Library_Zone, Total_Seats, Occupied_Seats,
  Available_Seats, Occupancy_Percentage, Day, Hour (+ Data_Source = SIMULATED).
- Realism: morning ramp-up, afternoon peak, weekend demand ~55% of weekdays, a 10% rise in the
  second week (exam preparation), different demand per zone, random noise, occupancy never
  above capacity.

### Data cleaning (show the Data Quality page)
"We added six bad rows on purpose to prove the cleaning works. The page shows: 1,146 total
records, 4 missing values, 1 duplicate, 1 invalid timestamp, 3 invalid occupancy readings →
1,141 clean records."
Walk through the rules:
1. Invalid timestamp (`2026-13-45 25:00:00`) → **excluded**.
2. Missing Total_Seats → **repaired** from the known seating layout (capacity is fixed).
3. Missing Occupied_Seats → **excluded** — "we do not invent a reading, because that would
   distort the KPIs".
4. Negative value or occupied > capacity (175 of 80 seats) → **excluded**.
5. Duplicate (same time and zone) → second copy **excluded**.
6. Available seats, percentage, day and hour are always **recalculated** from the source columns.
"Nothing is silently accepted — every issue is listed with its CSV line number and the action
taken. The raw file itself is never changed."

**Hand-over line:** "Now that the data is clean, Student 2 will explain what we measure and how we show it."

---

## Student 2 — KPIs, charts, filters and design (≈ 4–5 min)

**Pages to show:** Overview → Occupancy Analytics → Zone Analysis → Peak Hours

### KPIs (top of every analytics page)
| KPI | What it means | Current value |
|---|---|---|
| Total Library Seats | Capacity of all selected zones | 468 |
| Currently Occupied | Occupied seats in the **latest reading of each zone** | 422 (90.2%, "High") |
| Available Seats | Total − occupied | 46 |
| Overall Occupancy | Σ occupied ÷ Σ capacity over the selected period (seat-weighted) | 49.0% |
| Peak Occupancy | Highest library-wide % in any single hour | 90.4% (Thu 05 Nov, 15:00) |
| Busiest Zone | Zone with highest average occupancy | Silent Study Area (55.5%) |

"Why seat-weighted? A 150-seat hall at 50% is more people than a 40-seat room at 50%, so we
divide total occupied by total capacity instead of averaging percentages."

### Why each chart
- **A. Line chart — occupancy trend:** best for change over time. Hourly/Daily toggle and
  'split by zone'. The dotted red line marks 85% (high demand). Gaps = library closed overnight.
- **B. Horizontal bar — zone-wise occupancy:** bars compare values accurately; sorted to show ranking.
- **C. Peak-hours bar + heatmap:** busiest hours at a glance (top 3 highlighted); the
  day × hour heatmap adds the weekday/weekend pattern.
- **D. Stacked bar — occupied vs available:** full bar = capacity, so usage and spare seats
  appear together. Switch between "current snapshot" and "average over period".
- **E. Donut — distribution:** each zone's share of all seat-hours used (only 4 slices, readable).
- **F. Scatter — time of day vs occupancy:** every dot is one reading; weekday vs weekend
  colours; black line = hourly mean. **Talking point:** Pearson r ≈ 0.02 even though time
  clearly matters — because the relationship is curved (rises then falls), not linear.

"Every chart has a title, axis labels with units, tooltips on hover, and the same colour for a
zone on every chart. The palette was checked for colour-blind safety, and status labels use
text plus colour, never colour alone."

### Filters (demonstrate live)
1. Building → choose only **Engineering Library** → Total seats changes to **178**.
2. Time range → **8:00–10:00** → occupancy drops; insights change.
3. Zone → only **Group Study Area** → busiest zone and findings change.
4. Press **Reset filters**.
"Every KPI, chart, table and insight is recalculated from the filtered data. If no data
matches, the dashboard shows a warning instead of empty charts."

### Design
"Sidebar navigation with 7 sections, KPI cards in a responsive grid, consistent spacing and
typography, light and dark mode (⋮ → Settings), and it adapts to mobile screens."

**Hand-over line:** "Student 3 will now show how the dashboard reacts to new data, and what we learned."

---

## Student 3 — Real-time simulation, findings, recommendations, limitations (≈ 4 min)

**Pages to show:** Live Data Simulation → Overview (findings) → Data Quality (optional)

### Simulated real-time updates (demonstrate live)
"This is **simulated** real-time data — not a connection to campus sensors."
1. Note the current values: Clean records **1,141**, latest reading **Wed 11 Nov 15:00**.
2. **Manual record:** choose *Central Library · Ground Floor · Reading Hall*, enter e.g. **140**
   seats, date 11 Nov, time **16:00**, press **Submit record**.
   - Success message appears; 'Clean records' becomes **1,142** with a +1 delta; currently
     occupied and overall occupancy change; the last-48-hours chart extends to 16:00; the new
     row appears at the top of the CSV table.
3. **Validation:** try **200** seats for Group Study Area (capacity 48) → "Record rejected: cannot
   exceed the 48 seats". Nothing is written.
4. **Add random record:** press the button → a realistic reading for the next hour is generated
   using the same demand model.
5. Go back to **Overview** → KPIs and charts already include the new records.
"How it works: the record is appended to the CSV; the dashboard's cache is keyed on the CSV's
modification time, so it reloads the changed file and recalculates everything."
(After the demo: tick the checkbox and press **Restore original dataset**.)

### Findings (generated automatically from the data — not typed by us)
- Occupancy peaks at **15:00 (73.7% on average)**; the **afternoon** is the busiest period;
  08:00 is the quietest (19%).
- **Silent Study Area** has the highest demand (55.5%), 18 percentage points above
  **Group Study Area** (37.6%).
- Group Study Area has the most spare capacity — 62% of its seats are free on average.
- **Monday** is the busiest day; weekday occupancy is **1.8×** the weekend level.
- Silent Study Area is ≥ 90% full in **9.5%** of its readings — students are likely turned away.
- Occupancy rose from 46.9% to 51.2% in the second week (exam preparation).

### Recommendations
1. Silent Study Area averages ≥ 80% at 15:00 → open overflow rooms or seat booking at that time.
2. Redistribute seating: re-purpose part of the under-used Group Study Area for silent study.
3. Library is below 35% at 08:00–09:59 and 20:00–21:59 → schedule cleaning and maintenance then.
4. Weekend demand is much lower → reduced weekend staffing / close low-demand floors.
5. Show live seat availability on entrance screens and in a student app.

### Limitations
- Simulated data; real data would include sensor faults, holidays and events.
- Only 14 days — no semester-level patterns.
- Not truly real-time: updates happen when records are added, no streaming sensor link.
- CSV storage is not suitable for many simultaneous users; no login/authentication.
- Insights are rule-based thresholds, not predictions.

### Future improvements
Real IoT sensors via API, a database, automatic alerts above 90%, occupancy forecasting,
student mobile view with seat booking.

**Closing line:** "Our dashboard turns simple seat counts into decisions: where to add seats,
when to staff, and when to clean. Thank you — we are happy to take questions."

---

## Likely questions and answers (all three members should know these)

| Question | Answer |
|---|---|
| Is the data real? | No. It is simulated with `generate_data.py` (fixed random seed). The dashboard labels it as SIMULATED everywhere. |
| How many records? | 1,146 rows: 1,140 hourly readings + 6 deliberately flawed rows. 1,141 are clean. |
| How is occupancy % calculated? | Occupied ÷ Total × 100 for one reading. Overall % is Σ occupied ÷ Σ total (seat-weighted). |
| Why not average the percentages? | Small zones would count as much as large ones; seat-weighting reflects actual people. |
| What does "Currently occupied" mean? | Sum of the latest reading of each zone location. |
| How do you handle missing values? | Missing capacity → repaired from the known layout. Missing occupancy → excluded (we never invent a reading). Derived columns → recalculated. |
| How are duplicates detected? | Same timestamp + building + floor + zone. The first copy is kept. |
| What if someone enters 200 seats for a 48-seat zone? | The record is rejected with a message and not written to the CSV. |
| How does the dashboard know the CSV changed? | The cached data is keyed on the file's modification time and size; any change forces a reload. |
| Why is Pearson r almost zero in the scatter plot? | Occupancy rises until 15:00 and then falls — a curved relationship. Pearson r only measures straight-line relationships. |
| Why a donut and not a pie? | Same information; the centre shows the total. Only 4 zones, so it remains readable. |
| Are the insights hard-coded? | No. They are computed from the filtered data — change a filter and the text changes. |
| How did you test it? | 23 automated tests (pytest + Streamlit AppTest) for KPIs, filters, record adding, validation and data quality, plus browser checks in light, dark and mobile layouts. |
| How would you make it production-ready? | Real sensors via API, a database, authentication, alerts and forecasting. |
| Which libraries did you use? | Streamlit (UI), Pandas/NumPy (processing), Plotly (charts), CSV (storage). |
