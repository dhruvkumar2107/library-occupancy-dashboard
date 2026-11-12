"""
Campus Library Occupancy Monitoring Dashboard
=============================================
VII Semester B.Tech - Data Science and Visualization (flipped-classroom project)

Run:   streamlit run app.py

*** All data shown is SIMULATED. There is no connection to real campus sensors. ***
"""
from __future__ import annotations

import datetime as dt
import os

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import generate_data
import library_core as lc

st.set_page_config(page_title="Library Occupancy Monitor", page_icon=":material/local_library:",
                   layout="wide", initial_sidebar_state="auto")

# --------------------------------------------------------------------------- #
# Theme (light / dark follow Streamlit's Settings -> Theme)
# --------------------------------------------------------------------------- #
IS_DARK = (st.context.theme.type == "dark") if st.context.theme.type else False

if IS_DARK:
    T = dict(text="#f0efec", text2="#c3c2b7", muted="#8f8e88", grid="#33363d",
             card="#161a22", border="#2a2f3a", surface="#0e1117",
             zone={"Reading Hall": "#3987e5", "Digital Library": "#d95926",
                   "Group Study Area": "#199e70", "Silent Study Area": "#c98500"},
             occupied="#3987e5", available="#4a4d55", weekday="#3987e5", weekend="#d95926",
             bar_hi="#3987e5", bar_lo="#1c5cab", mean_line="#f0efec",
             seq=["#104281", "#184f95", "#1c5cab", "#256abf", "#2a78d6", "#3987e5",
                  "#5598e7", "#86b6ef", "#cde2fb"])
else:
    T = dict(text="#1f2328", text2="#52514e", muted="#8a8985", grid="#e7e6e2",
             card="#ffffff", border="#e4e2dd", surface="#ffffff",
             zone={"Reading Hall": "#2a78d6", "Digital Library": "#eb6834",
                   "Group Study Area": "#1baf7a", "Silent Study Area": "#eda100"},
             occupied="#2a78d6", available="#d3d1cb", weekday="#2a78d6", weekend="#eb6834",
             bar_hi="#256abf", bar_lo="#9ec5f4", mean_line="#1f2328",
             seq=["#f3f8fe", "#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#2a78d6",
                  "#1c5cab", "#104281", "#0d366b"])
STATUS = {"good": "#0ca30c", "warning": "#fab219", "serious": "#ec835a", "critical": "#d03b3b"}
FONT = "Inter, -apple-system, Segoe UI, Roboto, sans-serif"

st.markdown(f"""
<style>
  .block-container {{ padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1400px; }}
  .app-header {{ display:flex; flex-wrap:wrap; align-items:flex-end; justify-content:space-between;
                 gap:.75rem; margin-bottom: 1.1rem; }}
  .app-title {{ font-size: 1.65rem; font-weight: 700; letter-spacing: -.02em; color:{T['text']};
                margin:0; line-height:1.2; }}
  .app-sub {{ color:{T['text2']}; font-size:.92rem; margin-top:.2rem; }}
  .badge {{ display:inline-block; padding:.18rem .55rem; border-radius:999px; font-size:.72rem;
            font-weight:600; letter-spacing:.04em; border:1px solid {STATUS['warning']};
            color:{T['text']}; background: rgba(250,178,25,.14); vertical-align:middle; }}
  .meta {{ color:{T['text2']}; font-size:.82rem; text-align:right; line-height:1.5; }}
  .kpi-grid {{ display:grid; grid-template-columns: repeat(6, minmax(0, 1fr));
               gap: 12px; margin: .2rem 0 1.4rem 0; }}
  @media (max-width: 1280px) {{ .kpi-grid {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }} }}
  @media (max-width: 640px)  {{ .kpi-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }} }}
  .kpi {{ background:{T['card']}; border:1px solid {T['border']}; border-radius:12px;
          padding: 13px 14px 12px 14px; box-shadow: 0 1px 2px rgba(0,0,0,.04); }}
  .kpi-label {{ color:{T['text2']}; font-size:.72rem; font-weight:600; text-transform:uppercase;
                letter-spacing:.05em; }}
  .kpi-value {{ color:{T['text']}; font-size:1.75rem; font-weight:700; letter-spacing:-.02em;
                margin-top:.35rem; line-height:1.15; white-space:nowrap; overflow:hidden;
                text-overflow:ellipsis; }}
  .kpi-value.small {{ font-size:1.12rem; white-space:normal; line-height:1.25; padding-top:.2rem; }}
  .kpi-sub {{ color:{T['muted']}; font-size:.8rem; margin-top:.3rem; }}
  .pill {{ display:inline-flex; align-items:center; gap:.3rem; font-size:.74rem; font-weight:600;
           color:{T['text']}; padding:.05rem .45rem; border-radius:999px; margin-left:.3rem; }}
  .dot {{ width:8px; height:8px; border-radius:50%; display:inline-block; }}
  .section-note {{ color:{T['text2']}; font-size:.9rem; margin:-.4rem 0 1rem 0; }}
  div[data-testid="stSidebarNav"] {{ padding-top: .25rem; }}
</style>
""", unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
# Data loading (cache invalidates automatically whenever the CSV changes)
# --------------------------------------------------------------------------- #
@st.cache_data(show_spinner=False)
def load_data(mtime_ns: int, size: int):
    # mtime/size are part of the cache key, so any change to the CSV forces a reload
    raw = lc.load_raw()
    clean, report = lc.clean(raw)
    return raw, clean, report


def csv_signature():
    s = os.stat(lc.CSV_PATH)
    return s.st_mtime_ns, s.st_size


if not lc.CSV_PATH.exists():
    generate_data.main()
SIG = csv_signature()
RAW, DF, REPORT = load_data(*SIG)
CSV_MODIFIED = dt.datetime.fromtimestamp(SIG[0] / 1e9)

# --------------------------------------------------------------------------- #
# Filter state
# --------------------------------------------------------------------------- #
MIN_DATE, MAX_DATE = DF["Date"].min(), DF["Date"].max()
ALL_BUILDINGS = sorted(DF["Building"].unique())
ALL_FLOORS = [f for f in ["Ground Floor", "First Floor", "Second Floor"] if f in set(DF["Floor"])]
ALL_ZONES = [z for z in lc.ZONES if z in set(DF["Library_Zone"])]
HOURS = (generate_data.OPEN_HOUR, generate_data.CLOSE_HOUR)


def filter_defaults() -> dict:
    return {"f_dates": (MIN_DATE, MAX_DATE), "f_build": ALL_BUILDINGS, "f_floor": ALL_FLOORS,
            "f_zone": ALL_ZONES, "f_hours": HOURS}


def reset_filters() -> None:
    for k, v in filter_defaults().items():
        st.session_state[k] = v


for k, v in filter_defaults().items():
    st.session_state.setdefault(k, v)
if st.session_state.pop("_reset_filters", False):
    reset_filters()
if st.session_state.pop("_extend_dates", False):   # a new record was added
    start = st.session_state["f_dates"][0] if st.session_state["f_dates"] else MIN_DATE
    st.session_state["f_dates"] = (start, MAX_DATE)
# keep the stored date range inside the data bounds
_d = st.session_state["f_dates"]
if _d and (_d[0] < MIN_DATE or _d[-1] > MAX_DATE):
    st.session_state["f_dates"] = (max(_d[0], MIN_DATE), min(_d[-1], MAX_DATE))


# --------------------------------------------------------------------------- #
# Live-simulation callbacks (run before the script re-executes)
# --------------------------------------------------------------------------- #
def _after_append(record: dict, how: str, before: dict | None) -> None:
    st.session_state["_extend_dates"] = True
    st.session_state["_before_kpis"] = before
    st.session_state.setdefault("_added", []).append(record)
    st.session_state["_flash"] = ("success", f"{how} saved to `data/library_occupancy.csv` — "
                                  f"{record['Library_Zone']} ({record['Building']}, "
                                  f"{record['Floor']}) at {record['Timestamp']}: "
                                  f"{record['Occupied_Seats']}/{record['Total_Seats']} seats "
                                  f"occupied ({record['Occupancy_Percentage']:.1f}%).")


def cb_manual_record() -> None:
    raw, clean_df, _ = load_data(*csv_signature())
    loc = st.session_state["m_loc"]
    building, floor, zone = loc.split(" · ")
    try:
        ts = pd.Timestamp(dt.datetime.combine(st.session_state["m_date"],
                                              st.session_state["m_time"]))
        rec = lc.make_record(ts, building, floor, zone, st.session_state["m_occ"])
        if lc.is_duplicate(clean_df, rec):
            raise lc.RecordError("A reading for this zone at this exact time already exists "
                                 "(duplicate rejected).")
    except lc.RecordError as e:
        st.session_state["_flash"] = ("error", f"Record rejected: {e}")
        return
    before = lc.compute_kpis(clean_df)
    lc.append_record(rec)
    _after_append(rec, "Manual record", before)


def cb_random_records() -> None:
    raw, clean_df, _ = load_data(*csv_signature())
    before = lc.compute_kpis(clean_df)
    n = int(st.session_state.get("r_count", 1))
    rng = np.random.default_rng()
    work = clean_df
    for _ in range(n):
        rec = lc.random_record(work, rng)
        lc.append_record(rec)
        work = pd.concat([work, pd.DataFrame([{**rec, "Timestamp": pd.Timestamp(rec["Timestamp"])}])],
                         ignore_index=True)
        _after_append(rec, "Random record" if n == 1 else f"Random record ({_ + 1}/{n})", before)
    if n > 1:
        st.session_state["_flash"] = ("success", f"{n} random records generated and saved to "
                                      f"`data/library_occupancy.csv`.")


def cb_restore_dataset() -> None:
    generate_data.main()
    st.session_state["_reset_filters"] = True
    st.session_state["_added"] = []
    st.session_state["_before_kpis"] = None
    st.session_state["_flash"] = ("info", "Original simulated dataset restored "
                                  f"({len(lc.load_raw())} records).")


# --------------------------------------------------------------------------- #
# Formatting helpers
# --------------------------------------------------------------------------- #
def fmt_ts(ts) -> str:
    return pd.Timestamp(ts).strftime("%a %d %b %Y, %H:%M")


def status_of(pct: float) -> tuple[str, str]:
    if pct >= 85:
        return "critical", "High"
    if pct >= 60:
        return "warning", "Busy"
    return "good", "Normal"


def pill(pct: float) -> str:
    key, label = status_of(pct)
    return (f"<span class='pill'><span class='dot' style='background:{STATUS[key]}'></span>"
            f"{label}</span>")


def kpi_cards(df: pd.DataFrame) -> None:
    k = lc.compute_kpis(df)
    cards = [
        ("Total Library Seats", f"{k['total_seats']:,}", f"across {k['locations']} zone locations", ""),
        ("Currently Occupied", f"{k['current_occupied']:,}",
         f"{k['current_occupancy_pct']:.1f}% {pill(k['current_occupancy_pct'])}", ""),
        ("Available Seats", f"{k['available_seats']:,}",
         f"as of {pd.Timestamp(k['snapshot_time']).strftime('%d %b, %H:%M')}", ""),
        ("Overall Occupancy", f"{k['overall_occupancy_pct']:.1f}%",
         f"average of {k['records']:,} readings", ""),
        ("Peak Occupancy", f"{k['peak_occupancy_pct']:.1f}%",
         f"{pd.Timestamp(k['peak_time']).strftime('%a %d %b, %H:00')}", ""),
        ("Busiest Library Zone", k["busiest_zone"],
         f"{k['busiest_zone_pct']:.1f}% average occupancy", "small"),
    ]
    html = "".join(f"<div class='kpi'><div class='kpi-label'>{l}</div>"
                   f"<div class='kpi-value {c}' title='{v}'>{v}</div>"
                   f"<div class='kpi-sub'>{s}</div></div>" for l, v, s, c in cards)
    st.markdown(f"<div class='kpi-grid'>{html}</div>", unsafe_allow_html=True)


def style(fig: go.Figure, title: str, x_title: str = "", y_title: str = "",
          height: int = 380, legend: bool = True, subtitle: str = "") -> go.Figure:
    axis = dict(gridcolor=T["grid"], zerolinecolor=T["grid"], linecolor=T["grid"],
                tickfont=dict(color=T["text2"], size=12), title_font=dict(color=T["text2"], size=12.5),
                automargin=True)
    fig.update_layout(
        template="none", height=height, font=dict(family=FONT, color=T["text"], size=13),
        title=dict(text=f"<b>{title}</b>", x=0, xanchor="left", y=0.98, yanchor="top",
                   font=dict(size=15, color=T["text"]),
                   subtitle=dict(text=subtitle, font=dict(size=12, color=T["text2"]))),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=16, t=(64 if legend else 48) + (18 if subtitle else 0), b=10),
        showlegend=legend,
        legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="left", x=0,
                    font=dict(color=T["text2"], size=12), title_text=""),
        hoverlabel=dict(bgcolor=T["card"], bordercolor=T["border"],
                        font=dict(family=FONT, color=T["text"], size=12.5)),
    )
    fig.update_xaxes(title_text=x_title, showgrid=False, **axis)
    fig.update_yaxes(title_text=y_title, showgrid=True, **axis)
    return fig


def show(fig: go.Figure) -> None:
    st.plotly_chart(fig, width="stretch", theme=None,
                    config={"displaylogo": False, "modeBarButtonsToRemove": ["lasso2d", "select2d"]})


# --------------------------------------------------------------------------- #
# Charts
# --------------------------------------------------------------------------- #
def chart_trend(df, granularity="Hourly", split=False) -> go.Figure:
    fig = go.Figure()
    if granularity == "Hourly":
        data = lc.hourly_snapshots(df, by="Library_Zone" if split else None)
        x, fmt = "Slot", "%a %d %b, %H:00"
    else:
        data = lc.ratio_by(df, ["Date", "Library_Zone"] if split else "Date")
        x, fmt = "Date", "%a %d %b %Y"
    groups = [(z, data[data["Library_Zone"] == z], T["zone"][z]) for z in lc.ZONES
              if split and z in set(data["Library_Zone"])] or [("Library-wide", data, T["occupied"])]
    for name, d, color in groups:
        if granularity == "Hourly" and len(d):     # leave gaps while the library is closed
            full = pd.date_range(d["Slot"].min(), d["Slot"].max(), freq="h")
            d = d.set_index("Slot").reindex(full).rename_axis("Slot").reset_index()
        fig.add_trace(go.Scatter(
            x=d[x], y=d["Occupancy_Percentage"], name=name, mode="lines+markers" if granularity == "Daily" else "lines",
            line=dict(color=color, width=2), marker=dict(size=8, line=dict(width=2, color=T["surface"])),
            connectgaps=False,
            customdata=np.stack([d["Occupied_Seats"], d["Total_Seats"]], axis=-1),
            hovertemplate=f"<b>{name}</b><br>%{{x|{fmt}}}<br>Occupancy: %{{y:.1f}}%"
                          "<br>Occupied: %{customdata[0]:,} of %{customdata[1]:,} seat"
                          + ("s" if granularity == "Hourly" else "-hours") + "<extra></extra>"))
    fig.add_hline(y=85, line=dict(color=STATUS["critical"], width=1.5, dash="dot"),
                  annotation_text="85% high-demand threshold", annotation_position="top left",
                  annotation_font=dict(color=T["text2"], size=11))
    title = f"{granularity} occupancy trend" + (" by zone" if split else " (library-wide)")
    style(fig, title, "Date" if granularity == "Daily" else "Date and time", "Occupancy (%)",
          height=400, legend=split)
    fig.update_yaxes(range=[0, 105], ticksuffix="%")
    fig.update_layout(hovermode="x unified" if split else "closest")
    return fig


def chart_zone_bar(df) -> go.Figure:
    z = lc.ratio_by(df, "Library_Zone").sort_values("Occupancy_Percentage")
    fig = go.Figure(go.Bar(
        y=z["Library_Zone"], x=z["Occupancy_Percentage"], orientation="h",
        marker=dict(color=[T["zone"][n] for n in z["Library_Zone"]], cornerradius=4,
                    line=dict(width=0)),
        text=[f"{v:.1f}%" for v in z["Occupancy_Percentage"]], textposition="outside",
        textfont=dict(color=T["text"], size=12), cliponaxis=False,
        customdata=np.stack([z["Readings"], z["Avg_Available"]], axis=-1),
        hovertemplate="<b>%{y}</b><br>Average occupancy: %{x:.1f}%<br>"
                      "Average free seats per reading: %{customdata[1]:.1f}<br>"
                      "Readings: %{customdata[0]:,}<extra></extra>"))
    style(fig, "Zone-wise average occupancy", "Average occupancy (%)", "", height=340, legend=False)
    fig.update_xaxes(range=[0, 100], ticksuffix="%", showgrid=True)
    fig.update_yaxes(showgrid=False)
    fig.update_layout(bargap=0.35)
    return fig


def chart_peak_hours(df, height=360) -> go.Figure:
    s = lc.hourly_snapshots(df)
    h = s.groupby("Hour", as_index=False)["Occupancy_Percentage"].agg(["mean", "max"]).reset_index() \
        if False else s.groupby("Hour")["Occupancy_Percentage"].agg(["mean", "max"]).reset_index()
    top3 = set(h.nlargest(3, "mean")["Hour"])
    fig = go.Figure(go.Bar(
        x=h["Hour"], y=h["mean"],
        marker=dict(color=[T["bar_hi"] if v in top3 else T["bar_lo"] for v in h["Hour"]],
                    cornerradius=4),
        text=[f"{m:.0f}%" if hr in top3 else "" for hr, m in zip(h["Hour"], h["mean"])],
        textposition="outside", textfont=dict(color=T["text"], size=12), cliponaxis=False,
        customdata=np.stack([h["Hour"], h["Hour"], h["max"]], axis=-1),
        hovertemplate="<b>%{customdata[0]:02d}:00–%{customdata[1]:02d}:59</b><br>"
                      "Average occupancy: %{y:.1f}%<br>Highest recorded: %{customdata[2]:.1f}%"
                      "<extra></extra>"))
    style(fig, "Peak hours of the day", "Hour of day (24 h clock)", "Average occupancy (%)",
          height=height, legend=False,
          subtitle="Average library-wide occupancy per hour · top 3 hours highlighted")
    fig.update_xaxes(tickmode="array", tickvals=h["Hour"], tickangle=0,
                     ticktext=[f"{v:02d}" for v in h["Hour"]])
    fig.update_yaxes(range=[0, 100], ticksuffix="%")
    fig.update_layout(bargap=0.25)
    return fig


def chart_stacked(df, mode="Current snapshot") -> go.Figure:
    if mode == "Current snapshot":
        g = lc.latest_snapshot(df).groupby("Library_Zone", as_index=False)[
            ["Occupied_Seats", "Total_Seats"]].sum()
        sub = "latest reading per location"
    else:
        s = lc.hourly_snapshots(df, by="Library_Zone")
        g = s.groupby("Library_Zone", as_index=False)[["Occupied_Seats", "Total_Seats"]].mean()
        sub = "average per hour over selected period"
    g["Available_Seats"] = g["Total_Seats"] - g["Occupied_Seats"]
    g["pct"] = g["Occupied_Seats"] / g["Total_Seats"] * 100
    g = g.set_index("Library_Zone").reindex([z for z in lc.ZONES if z in set(g["Library_Zone"])]).reset_index()
    fig = go.Figure()
    for col, name, color in [("Occupied_Seats", "Occupied seats", T["occupied"]),
                             ("Available_Seats", "Available seats", T["available"])]:
        fig.add_trace(go.Bar(
            x=g["Library_Zone"], y=g[col], name=name,
            marker=dict(color=color, line=dict(color=T["surface"], width=2)),
            customdata=np.stack([g["Total_Seats"], g["pct"]], axis=-1),
            hovertemplate=f"<b>%{{x}}</b><br>{name}: %{{y:,.0f}}<br>"
                          "Total seats: %{customdata[0]:,.0f}<br>Occupancy: %{customdata[1]:.1f}%"
                          "<extra></extra>"))
    style(fig, f"Occupied vs available seats by zone ({sub})", "Library zone", "Seats",
          height=380)
    fig.update_layout(barmode="stack", bargap=0.45)
    return fig


def chart_donut(df) -> go.Figure:
    z = lc.ratio_by(df, "Library_Zone")
    z = z.set_index("Library_Zone").reindex([n for n in lc.ZONES if n in set(z["Library_Zone"])]).reset_index()
    fig = go.Figure(go.Pie(
        labels=z["Library_Zone"], values=z["Occupied_Seats"], hole=0.62, sort=False,
        marker=dict(colors=[T["zone"][n] for n in z["Library_Zone"]],
                    line=dict(color=T["surface"], width=2)),
        textinfo="percent", textfont=dict(color="#ffffff", size=12),
        hovertemplate="<b>%{label}</b><br>Occupied seat-hours: %{value:,}<br>"
                      "Share of all usage: %{percent}<extra></extra>"))
    total = int(z["Occupied_Seats"].sum())
    fig.add_annotation(text=f"<b>{total:,}</b><br><span style='font-size:11px'>seat-hours used</span>",
                       showarrow=False, font=dict(size=17, color=T["text"]))
    style(fig, "Occupancy distribution across zones (share of seat-hours)", height=340)
    fig.update_layout(legend=dict(orientation="v", y=0.5, yanchor="middle", x=1.02, xanchor="left"),
                      margin=dict(t=56))
    return fig


def chart_scatter(df) -> go.Figure:
    rng = np.random.default_rng(7)
    x = df["Hour"] + df["Timestamp"].dt.minute / 60 + rng.uniform(-0.28, 0.28, len(df))
    fig = go.Figure()
    for typ in ["Weekday", "Weekend"]:
        m = df["Day_Type"] == typ
        if not m.any():
            continue
        d = df[m]
        fig.add_trace(go.Scatter(
            x=x[m], y=d["Occupancy_Percentage"], mode="markers", name=typ,
            marker=dict(size=7, color=T[typ.lower()], opacity=0.55,
                        line=dict(width=0.5, color=T["surface"])),
            customdata=np.stack([d["Location"], d["Timestamp"].dt.strftime("%a %d %b %H:%M"),
                                 d["Occupied_Seats"], d["Total_Seats"]], axis=-1),
            hovertemplate="<b>%{customdata[0]}</b><br>%{customdata[1]}<br>"
                          "Occupancy: %{y:.1f}% (%{customdata[2]} of %{customdata[3]} seats)"
                          "<extra>" + typ + "</extra>"))
    mean = df.groupby("Hour")["Occupancy_Percentage"].mean()
    fig.add_trace(go.Scatter(x=mean.index, y=mean.values, name="Hourly mean (all zones)",
                             mode="lines", line=dict(color=T["mean_line"], width=2.5),
                             hovertemplate="%{x:02d}:00 mean: %{y:.1f}%<extra></extra>"))
    corr = df["Hour"].corr(df["Occupancy_Percentage"])
    style(fig, "Relationship: time of day vs occupancy", "Hour of day (24 h clock)",
          "Occupancy (%)", height=440,
          subtitle=f"Each dot is one zone reading · Pearson r = {corr:.2f}"
                   + (" — near zero because the pattern is curved (rises to an afternoon peak, "
                      "then falls), not linear" if abs(corr) < 0.3 else ""))
    fig.update_xaxes(tickmode="array", tickvals=list(range(8, 22)), tickangle=0,
                     ticktext=[f"{h:02d}:00" for h in range(8, 22)])
    fig.update_yaxes(range=[-2, 104], ticksuffix="%")
    return fig


def chart_heatmap(df) -> go.Figure:
    s = lc.hourly_snapshots(df)
    p = s.pivot_table(index="Day", columns="Hour", values="Occupancy_Percentage", aggfunc="mean")
    p = p.reindex([d for d in lc.DAY_ORDER if d in p.index])
    fig = go.Figure(go.Heatmap(
        z=p.values, x=[f"{h:02d}:00" for h in p.columns], y=p.index, zmin=0, zmax=100,
        colorscale=[[i / (len(T["seq"]) - 1), c] for i, c in enumerate(T["seq"])],
        xgap=2, ygap=2,
        colorbar=dict(title=dict(text="Occupancy %", font=dict(color=T["text2"], size=12)),
                      ticksuffix="%", tickfont=dict(color=T["text2"]), outlinewidth=0, thickness=12),
        hovertemplate="<b>%{y}, %{x}</b><br>Average occupancy: %{z:.1f}%<extra></extra>"))
    style(fig, "When is the library busiest?", "Hour of day (24 h clock)", "Day of week",
          height=390, legend=False, subtitle="Average library-wide occupancy by day of week and hour")
    fig.update_yaxes(autorange="reversed", showgrid=False)
    return fig


# --------------------------------------------------------------------------- #
# Sidebar: navigation + filters
# --------------------------------------------------------------------------- #
def header(title: str, subtitle: str) -> None:
    latest = DF["Timestamp"].max()
    st.markdown(f"""
    <div class="app-header">
      <div><div class="app-title">{title} <span class="badge">SIMULATED DATA</span></div>
           <div class="app-sub">{subtitle}</div></div>
      <div class="meta">Latest reading: <b>{fmt_ts(latest)}</b><br>
           Dataset updated: {CSV_MODIFIED.strftime('%d %b %Y, %H:%M:%S')} · {len(RAW):,} records</div>
    </div>""", unsafe_allow_html=True)


def filtered() -> pd.DataFrame:
    d = st.session_state["f_dates"]
    dates = (d[0], d[-1]) if d else None
    return lc.apply_filters(DF, dates, st.session_state["f_build"], st.session_state["f_floor"],
                            st.session_state["f_zone"], st.session_state["f_hours"])


def need_data(df) -> None:
    if df.empty:
        st.warning("No records match the current filters. Widen the filters or press "
                   "**Reset filters** in the sidebar.", icon=":material/filter_alt_off:")
        st.stop()


def filter_caption(df) -> None:
    st.caption(f"Showing **{len(df):,}** of {len(DF):,} clean records · "
               f"{df['Date'].min():%d %b} – {df['Date'].max():%d %b %Y} · "
               f"{st.session_state['f_hours'][0]:02d}:00–{st.session_state['f_hours'][1]:02d}:59")


# --------------------------------------------------------------------------- #
# Pages
# --------------------------------------------------------------------------- #
def page_overview():
    header("Campus Library Occupancy", "Real-time style monitoring of seating demand across "
           "campus libraries")
    df = filtered(); need_data(df)
    kpi_cards(df)
    filter_caption(df)
    show(chart_trend(df, "Hourly"))
    c1, c2 = st.columns(2, gap="medium")
    with c1:
        show(chart_zone_bar(df))
    with c2:
        show(chart_peak_hours(df, height=340))
    findings, recs = lc.generate_insights(df)
    c1, c2 = st.columns(2, gap="medium")
    with c1, st.container(border=True):
        st.markdown("##### :material/insights: Key findings")
        st.markdown("\n".join(f"- {f}" for f in findings))
    with c2, st.container(border=True):
        st.markdown("##### :material/task_alt: Recommendations for administrators")
        st.markdown("\n".join(f"- {r}" for r in recs))
    st.caption("Findings and recommendations are generated automatically from the filtered data "
               "and change when filters or records change.")


def page_occupancy():
    header("Occupancy Analytics", "How occupancy changes over time and through the day")
    df = filtered(); need_data(df)
    kpi_cards(df)
    c1, c2, _ = st.columns([1.2, 1.4, 3])
    gran = c1.segmented_control("Granularity", ["Hourly", "Daily"], default="Hourly",
                                key="trend_gran") or "Hourly"
    split = c2.toggle("Split by library zone", value=False, key="trend_split")
    show(chart_trend(df, gran, split))
    show(chart_scatter(df))
    st.caption("Dots are jittered horizontally within each hour so overlapping readings stay "
               "visible. The line shows the mean occupancy for each hour.")
    st.markdown("##### Daily summary")
    snaps = lc.hourly_snapshots(df)
    daily = lc.ratio_by(df, "Date")[["Date", "Occupancy_Percentage"]]
    pk = snaps.loc[snaps.groupby("Date")["Occupancy_Percentage"].idxmax(), ["Date", "Hour",
                                                                           "Occupancy_Percentage"]]
    daily = daily.merge(pk.rename(columns={"Occupancy_Percentage": "Peak_%", "Hour": "Peak_Hour"}),
                        on="Date")
    daily["Day"] = pd.to_datetime(daily["Date"]).dt.day_name()
    daily["Peak_Hour"] = daily["Peak_Hour"].map(lambda h: f"{h:02d}:00")
    st.dataframe(daily[["Date", "Day", "Occupancy_Percentage", "Peak_%", "Peak_Hour"]]
                 .sort_values("Date", ascending=False), hide_index=True, width="stretch",
                 column_config={"Occupancy_Percentage": st.column_config.ProgressColumn(
                     "Average occupancy", format="%.1f%%", min_value=0, max_value=100),
                     "Peak_%": st.column_config.NumberColumn("Peak occupancy", format="%.1f%%"),
                     "Peak_Hour": "Peak hour"})


def page_zones():
    header("Zone Analysis", "Comparing demand and spare capacity across library zones")
    df = filtered(); need_data(df)
    kpi_cards(df)
    c1, c2 = st.columns(2, gap="medium")
    with c1:
        show(chart_zone_bar(df))
    with c2:
        show(chart_donut(df))
    mode = st.segmented_control("Seat comparison", ["Current snapshot", "Average over period"],
                                default="Current snapshot", key="stack_mode") or "Current snapshot"
    show(chart_stacked(df, mode))
    st.markdown("##### Zone summary")
    z = lc.ratio_by(df, "Library_Zone")
    extra = df.groupby("Library_Zone").agg(
        Locations=("Location", "nunique"),
        Peak=("Occupancy_Percentage", "max"),
        Near_Full=("Occupancy_Percentage", lambda s: (s >= 90).mean() * 100)).reset_index()
    seats = lc.latest_snapshot(df).groupby("Library_Zone")["Total_Seats"].sum().rename("Seats")
    z = z.merge(extra, on="Library_Zone").merge(seats, on="Library_Zone")
    st.dataframe(z[["Library_Zone", "Locations", "Seats", "Occupancy_Percentage", "Peak",
                    "Avg_Available", "Near_Full"]].sort_values("Occupancy_Percentage", ascending=False),
                 hide_index=True, width="stretch", column_config={
                     "Library_Zone": "Zone",
                     "Occupancy_Percentage": st.column_config.ProgressColumn(
                         "Average occupancy", format="%.1f%%", min_value=0, max_value=100),
                     "Peak": st.column_config.NumberColumn("Peak reading", format="%.1f%%"),
                     "Avg_Available": st.column_config.NumberColumn("Avg free seats / reading",
                                                                    format="%.1f"),
                     "Near_Full": st.column_config.NumberColumn("Readings ≥ 90% full",
                                                                format="%.1f%%")})


def page_peak():
    header("Peak Hours", "Identifying the busiest hours and days")
    df = filtered(); need_data(df)
    kpi_cards(df)
    show(chart_peak_hours(df))
    show(chart_heatmap(df))
    st.markdown("##### Top 10 busiest hourly snapshots")
    s = lc.hourly_snapshots(df).nlargest(10, "Occupancy_Percentage")
    s["Time"] = s["Slot"].dt.strftime("%a %d %b %Y, %H:00")
    s["Available"] = s["Total_Seats"] - s["Occupied_Seats"]
    st.dataframe(s[["Time", "Occupied_Seats", "Available", "Total_Seats", "Occupancy_Percentage"]],
                 hide_index=True, width="stretch", column_config={
                     "Occupied_Seats": "Occupied", "Total_Seats": "Total seats",
                     "Occupancy_Percentage": st.column_config.ProgressColumn(
                         "Occupancy", format="%.1f%%", min_value=0, max_value=100)})


def page_live():
    header("Live Data Simulation", "Add new occupancy readings and watch the dashboard update")
    st.info("**Simulated real-time data.** This module imitates a sensor feed by writing new "
            "records into `data/library_occupancy.csv`. It is **not** connected to real campus "
            "sensors. Every saved record is validated, written to the CSV, and the dashboard "
            "reloads from the updated file.", icon=":material/sensors:")

    flash = st.session_state.pop("_flash", None)
    if flash:
        getattr(st, flash[0])(flash[1], icon={"success": ":material/check_circle:",
                                             "error": ":material/error:",
                                             "info": ":material/info:"}[flash[0]])

    locs = [f"{b} · {f} · {z}" for b, f, z, *_ in generate_data.LOCATIONS]
    latest = DF["Timestamp"].max()
    nxt = latest.floor("h") + pd.Timedelta(minutes=30)
    st.session_state.setdefault("m_date", nxt.date())
    st.session_state.setdefault("m_time", nxt.time())

    c1, c2 = st.columns([1.35, 1], gap="large")
    with c1, st.container(border=True):
        st.markdown("##### :material/edit_note: Add a record manually")
        with st.form("manual", clear_on_submit=False, border=False):
            st.selectbox("Library zone (building · floor · zone)", locs, key="m_loc")
            st.number_input("Occupied seats", min_value=0, step=1, value=40, key="m_occ",
                            help="Validated against the selected zone's seat capacity.")
            a, b = st.columns(2)
            a.date_input("Date", key="m_date")
            b.time_input("Time", key="m_time", step=dt.timedelta(minutes=15))
            st.caption("Capacity: " + " · ".join(f"{z} ({b.split()[0]}) {s}"
                                                 for b, f, z, s, _ in generate_data.LOCATIONS))
            st.form_submit_button("Submit record", type="primary", icon=":material/add:",
                                  on_click=cb_manual_record)
    with c2, st.container(border=True):
        st.markdown("##### :material/casino: Generate a random reading")
        st.caption("Creates a realistic reading for the next hourly slot after the latest record, "
                   "using the same time-of-day / weekday / zone demand model as the dataset.")
        st.slider("Number of records", 1, 10, 1, key="r_count")
        st.button("Add random record", type="primary", icon=":material/bolt:",
                  on_click=cb_random_records, width="stretch")
        st.divider()
        st.caption("Reset the CSV to the original generated dataset (removes all added records).")
        ok = st.checkbox("I understand added records will be deleted", key="restore_ok")
        st.button("Restore original dataset", icon=":material/restart_alt:", disabled=not ok,
                  on_click=cb_restore_dataset, width="stretch")

    # --- What changed ---
    before = st.session_state.get("_before_kpis")
    after = lc.compute_kpis(DF)
    st.markdown("##### :material/monitoring: Dashboard state (full dataset, recalculated from the CSV)")
    m = st.columns(4)
    def delta(key, fmt="{:+,.0f}"):
        return fmt.format(after[key] - before[key]) if before else None
    m[0].metric("Clean records", f"{after['records']:,}", delta("records"), border=True)
    m[1].metric("Currently occupied", f"{after['current_occupied']:,}", delta("current_occupied"),
                border=True, delta_color="off")
    m[2].metric("Available seats", f"{after['available_seats']:,}", delta("available_seats"),
                border=True, delta_color="off")
    m[3].metric("Overall occupancy", f"{after['overall_occupancy_pct']:.2f}%",
                delta("overall_occupancy_pct", "{:+.2f} pp"), border=True,
                delta_color="off")
    st.caption(f"Latest reading in the dataset: **{fmt_ts(after['snapshot_time'])}** · CSV last "
               f"modified: **{CSV_MODIFIED.strftime('%d %b %Y, %H:%M:%S')}** · {len(RAW):,} raw rows"
               + (" · deltas compare the dashboard before and after the most recent addition."
                  if before else ""))

    added = st.session_state.get("_added", [])
    if added:
        st.markdown("##### Latest added record")
        st.dataframe(pd.DataFrame([added[-1]]), hide_index=True, width="stretch")
    df = filtered()
    if not df.empty:
        show(chart_trend(df[df["Timestamp"] >= df["Timestamp"].max() - pd.Timedelta(days=2)],
                         "Hourly", split=True))
        st.caption("Last 48 hours of the filtered data — newly added records appear at the right "
                   "edge of the chart.")
    st.markdown("##### Last 10 rows of `data/library_occupancy.csv` (raw file)")
    st.dataframe(RAW.tail(10).iloc[::-1], width="stretch")


def page_quality():
    header("Data Quality", "Validation and cleaning applied before any KPI is calculated")
    r = REPORT
    items = [("Total records", r.total_records), ("Missing values", r.missing_total),
             ("Duplicate records", r.duplicate_records), ("Invalid timestamps", r.invalid_timestamps),
             ("Invalid occupancy readings", r.invalid_occupancy),
             ("Clean records used", r.clean_records)]
    for row in (items[:3], items[3:]):
        for c, (label, v) in zip(st.columns(3), row):
            c.metric(label, f"{v:,}", border=True)

    st.markdown("##### Records with issues and the action taken")
    if r.issues.empty:
        st.success("No data-quality issues found.")
    else:
        st.dataframe(r.issues.sort_values("CSV_Row")[["CSV_Row", "Issue", "Action", "Timestamp",
                                                       "Building", "Library_Zone",
                                                       "Occupied_Seats"]],
                     hide_index=True, width="stretch",
                     column_config={"CSV_Row": st.column_config.NumberColumn("CSV line",
                                                                             format="%d")})
    excluded = int((r.issues["Action"] == "Excluded").sum()) if not r.issues.empty else 0
    st.markdown(f"**Summary:** {r.total_records:,} raw records → {excluded} excluded, "
                f"{r.repaired_records} repaired, {r.recalculated_fields} with derived fields "
                f"recalculated → **{r.clean_records:,} clean records** used by every KPI and "
                f"chart. Unknown locations: {r.unknown_location}.")

    c1, c2 = st.columns([1, 1.7], gap="large")
    with c1:
        st.markdown("##### Missing values by column (raw CSV)")
        mv = pd.DataFrame({"Column": list(r.missing_by_column),
                           "Missing": list(r.missing_by_column.values())})
        mv["% of rows"] = mv["Missing"] / max(r.total_records, 1) * 100
        st.dataframe(mv, hide_index=True, width="stretch", height=422,
                     column_config={"% of rows": st.column_config.NumberColumn(format="%.2f%%")})
    with c2:
        with st.container(border=True):
            st.markdown("##### :material/cleaning_services: Data-cleaning process")
            st.markdown("""
1. **Timestamp validation** — timestamps are parsed with the strict format `YYYY-MM-DD HH:MM:SS`. Missing or impossible dates (e.g. month 13, hour 25) are **excluded**.
2. **Location validation** — each Building / Floor / Zone must exist in the known seating layout; unknown locations are **excluded**.
3. **Missing capacity** — a missing `Total_Seats` is **repaired** from the known seating layout, because a zone's capacity is fixed metadata.
4. **Missing occupancy reading** — a missing `Occupied_Seats` is **excluded**, not guessed: inventing a sensor reading would distort the KPIs.
5. **Impossible readings** — negative values or `Occupied_Seats > Total_Seats` are **excluded** and listed above (never silently accepted).
6. **Duplicates** — readings with the same timestamp and location are detected; the first is kept and later copies are **excluded**.
7. **Derived fields recalculated** — `Available_Seats = Total_Seats − Occupied_Seats`, `Occupancy_Percentage = Occupied / Total × 100`, `Day` and `Hour` are always recomputed from the source columns, so they can never be inconsistent.

The raw CSV is never modified by cleaning — issues stay visible here for auditing.
""")
    st.caption("Note: the dataset intentionally contains a few flawed rows (appended by "
               "`generate_data.py`) to demonstrate that this validation works.")


def page_info():
    header("Project Information", "VII Semester B.Tech · Data Science and Visualization · "
           "Flipped-classroom assignment")
    st.warning("All data in this dashboard is **SIMULATED** for academic purposes. It does not "
               "represent any real library or real students.", icon=":material/science:")
    c1, c2 = st.columns(2, gap="large")
    with c1:
        st.markdown("""
#### Objective
Help library administrators **monitor occupancy, identify peak hours, understand seating demand**
and make better decisions about library resources.

#### Problem statement
Students often walk to a full library zone while other zones have free seats, and administrators
lack data on when and where demand peaks. This dashboard turns hourly seat-occupancy readings
into KPIs, trends and recommendations.

#### Intended users
- **Library administrators** — daily monitoring and staffing
- **College management** — capacity planning and budgeting
- **Students** — finding a free seat quickly
- **Campus facility managers** — cleaning, maintenance and energy scheduling

#### Technology stack
Python · Streamlit (UI) · Pandas (processing) · Plotly (interactive charts) · CSV (storage)
""")
    with c2:
        st.markdown("#### KPI definitions")
        st.dataframe(pd.DataFrame([
            ("Total Library Seats", "Sum of seat capacity of all selected zone locations"),
            ("Currently Occupied", "Sum of occupied seats in the latest reading of each location"),
            ("Available Seats", "Total Library Seats − Currently Occupied"),
            ("Overall Occupancy %", "Σ occupied seats ÷ Σ total seats over all readings in the "
                                    "selected period (seat-weighted average)"),
            ("Peak Occupancy", "Highest library-wide occupancy % in any single hour (with time)"),
            ("Busiest Library Zone", "Zone with the highest seat-weighted average occupancy %"),
        ], columns=["KPI", "Definition"]), hide_index=True, width="stretch")
        st.markdown("""
#### Dataset
`data/library_occupancy.csv` — hourly readings (08:00–21:00) for 6 zone locations in
2 libraries over 14 days, plus a few deliberately flawed rows for data-quality testing.

#### Navigation
Overview · Occupancy Analytics · Zone Analysis · Peak Hours · Live Data Simulation ·
Data Quality · Project Information. All analytics pages respond to the sidebar filters.
""")


# --------------------------------------------------------------------------- #
# App shell
# --------------------------------------------------------------------------- #
START_PAGE = os.environ.get("DASHBOARD_START_PAGE", "overview")   # used by automated tests
PAGES = {
    "Analytics": [
        (page_overview, "Overview", ":material/dashboard:", "overview"),
        (page_occupancy, "Occupancy Analytics", ":material/show_chart:", "occupancy"),
        (page_zones, "Zone Analysis", ":material/grid_view:", "zones"),
        (page_peak, "Peak Hours", ":material/schedule:", "peak-hours"),
    ],
    "Data": [
        (page_live, "Live Data Simulation", ":material/sensors:", "live"),
        (page_quality, "Data Quality", ":material/fact_check:", "data-quality"),
    ],
    "About": [(page_info, "Project Information", ":material/info:", "about")],
}
nav = st.navigation({
    section: [st.Page(fn, title=t, icon=i, url_path=u, default=(u == START_PAGE))
              for fn, t, i, u in items]
    for section, items in PAGES.items()})

with st.sidebar:
    st.markdown("### :material/filter_alt: Filters")
    st.date_input("Date range", key="f_dates", min_value=MIN_DATE, max_value=MAX_DATE,
                  format="DD/MM/YYYY")
    st.multiselect("Building", ALL_BUILDINGS, key="f_build", placeholder="Choose buildings")
    st.multiselect("Floor", ALL_FLOORS, key="f_floor", placeholder="Choose floors")
    st.multiselect("Library zone", ALL_ZONES, key="f_zone", placeholder="Choose zones")
    st.slider("Time range (hour of day)", HOURS[0], HOURS[1], key="f_hours",
              format="%d:00")
    st.button("Reset filters", icon=":material/restart_alt:", on_click=reset_filters,
              width="stretch")
    st.caption("Filters apply to every KPI and chart. Theme: ⋮ menu → Settings → "
               "Light / Dark.")

nav.run()
