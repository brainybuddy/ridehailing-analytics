"""
cluster_dashboard.py
--------------------
Lagos Rider Intelligence — 3-pillar dashboard

Sections:
  1. Rider Segments     — 7 colour-coded executive summary cards
  2. When They Ride     — hour-of-day + day-of-week charts by segment
  3. Origin–Destination — corridor map + rider table + similarity finder
  4. Rider Lookup       — find any rider by ID + 10 most similar riders

Run:
  streamlit run cluster_dashboard.py
"""

import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from sklearn.neighbors import NearestNeighbors

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Lagos Rider Intelligence",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
  .seg-card {
      padding: 14px 18px; border-radius: 10px;
      margin-bottom: 8px; color: white;
  }
  .card-title  { font-size: 15px; font-weight: 700; margin-bottom: 2px; }
  .card-count  { font-size: 24px; font-weight: 900; line-height: 1.2; }
  .card-pct    { font-size: 12px; opacity: 0.85; }
  .card-stats  { font-size: 12px; margin-top: 8px; line-height: 1.8; }
</style>
""", unsafe_allow_html=True)

# ── Colour palette (7 segments) ───────────────────────────────────────────────
COLORS = {
    0: "#2563EB",   # blue
    1: "#16A34A",   # green
    2: "#DC2626",   # red
    3: "#D97706",   # amber
    4: "#7C3AED",   # purple
    5: "#0891B2",   # cyan
    6: "#BE185D",   # pink
}

# ── Data loaders ──────────────────────────────────────────────────────────────
@st.cache_data
def load_features_pii():
    feat = pd.read_csv("full_user_features.csv")
    pii  = pd.read_csv("full_user_pii.csv", dtype=str)
    feat = feat.merge(
        pii[["rider_id", "full_name", "email", "phone_number", "home_area", "work_area"]],
        on="rider_id", how="left",
    )
    return feat


@st.cache_data
def load_route_data():
    rp  = pd.read_csv("full_user_route_profiles.csv")
    rg  = pd.read_csv("full_route_groups.csv")
    pii = pd.read_csv("full_user_pii.csv", dtype=str)
    rp  = rp.merge(
        pii[["rider_id", "full_name", "email", "phone_number", "home_area", "work_area"]],
        on="rider_id", how="left",
    )
    return rp, rg


@st.cache_data
def load_trip_zones():
    tz = pd.read_csv("full_trips_zones.csv", dtype=str)
    for col in ("start_lat", "start_lon", "end_lat", "end_lon"):
        tz[col] = pd.to_numeric(tz[col], errors="coerce")
    tz["hour"] = pd.to_numeric(tz["hour"], errors="coerce")
    tz["dow"]  = pd.to_numeric(tz["dow"],  errors="coerce")
    return tz


@st.cache_data
def load_viz_trips():
    viz = pd.read_csv("viz_trips.csv", dtype=str)
    viz["hour"] = pd.to_numeric(viz["hour"], errors="coerce")
    viz["dow"]  = pd.to_numeric(viz["dow"],  errors="coerce")
    return viz


@st.cache_data
def get_corridor_trips(rider_ids_tuple):
    tz = load_trip_zones()
    return tz[tz["rider_id"].isin(set(rider_ids_tuple))].copy()


# ── Load core data ────────────────────────────────────────────────────────────
feat        = load_features_pii()
rp, rg      = load_route_data()
cluster_ids = sorted(feat["cluster"].unique())
label_map   = feat.groupby("cluster")["cluster_label"].first().to_dict()

# Make labels unique — append A/B when the same name appears on multiple clusters
def _make_unique_labels(lmap):
    from collections import Counter
    counts = Counter(lmap.values())
    seen   = {}
    result = {}
    for cid in sorted(lmap):
        name = lmap[cid]
        if counts[name] > 1:
            seen[name] = seen.get(name, 0) + 1
            result[cid] = f"{name} {'ABCDEFG'[seen[name]-1]}"
        else:
            result[cid] = name
    return result

label_map = _make_unique_labels(label_map)


# ── Top corridor per segment (for cards) ─────────────────────────────────────
@st.cache_data
def top_corridor_per_cluster():
    # rp already has a 'cluster' column — use it directly
    merged = rp[rp["corridor_label"].notna()].copy()
    merged = merged[merged["corridor_label"] != "Mixed routes"]
    # Exclude labels with missing pickup zone (contain "→" as first non-space char)
    merged = merged[~merged["corridor_label"].str.strip().str.startswith("→", na=False)]
    # Exclude same-zone corridors
    merged = merged[merged["corridor_id"].apply(
        lambda x: x.split("__")[0] != x.split("__")[1] if "__" in str(x) else True
    )]
    result = {}
    for cid in cluster_ids:
        sub = merged[merged["cluster"] == cid]["corridor_label"]
        result[cid] = sub.value_counts().idxmax() if len(sub) > 0 else "—"
    return result


top_corridor = top_corridor_per_cluster()

# ── Sidebar ───────────────────────────────────────────────────────────────────
st.sidebar.title("Filters")
selected_clusters = st.sidebar.multiselect(
    "Segments",
    options=cluster_ids,
    default=cluster_ids,
    format_func=lambda x: label_map[x],
)

if not selected_clusters:
    st.warning("Select at least one segment in the sidebar.")
    st.stop()

feat_sel = feat[feat["cluster"].isin(selected_clusters)]

# ── Header ────────────────────────────────────────────────────────────────────
st.title("Lagos Rider Intelligence")
st.caption("Lagos, Nigeria")

# ── Summary metric cards ─────────────────────────────────────────────────────
@st.cache_data
def count_raw_trips():
    import glob
    files = glob.glob("lagosride.trip_requests.export*.csv")
    return sum(len(pd.read_csv(f)) for f in files)

pii = pd.read_csv("full_user_pii.csv", dtype=str)
total_trips = count_raw_trips()
total_users = len(pii)
total_riders = len(feat)
total_corridors = len(rg)

m1, m2, m3, m4 = st.columns(4)
m1.metric("Total Trips", f"{total_trips:,}")
m2.metric("Total Users", f"{total_users:,}")
m3.metric("Clustered Riders", f"{total_riders:,}")
m4.metric("Corridors", f"{total_corridors:,}")

st.markdown("---")

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — RIDER SEGMENTS
# ══════════════════════════════════════════════════════════════════════════════
st.subheader("1. Rider Segments")

cols = st.columns(len(cluster_ids))
for col, cid in zip(cols, cluster_ids):
    g         = feat[feat["cluster"] == cid]
    bg        = COLORS.get(cid, "#6B7280")
    pct       = len(g) / len(feat) * 100
    avg_trips = int(round(g["trips_per_week"].mean()))
    peak_hour = int(round(g["avg_hour"].mean()))
    top_corr  = top_corridor.get(cid, "—")
    with col:
        st.markdown(f"""
        <div class="seg-card" style="background:{bg}">
          <div class="card-title">{label_map[cid]}</div>
          <div class="card-count">{len(g):,}</div>
          <div class="card-pct">{pct:.0f}% of riders</div>
          <div class="card-stats">
            ✦ {avg_trips} trips/week<br>
            ✦ Peak: {peak_hour}:00<br>
            ✦ {top_corr}
          </div>
        </div>
        """, unsafe_allow_html=True)

st.markdown("---")

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — WHEN THEY RIDE
# ══════════════════════════════════════════════════════════════════════════════
st.subheader("2. When They Ride")

viz        = load_viz_trips()
viz_merged = viz.merge(feat[["rider_id", "cluster", "cluster_label"]], on="rider_id", how="left")
viz_sel    = viz_merged[viz_merged["cluster"].isin(selected_clusters)]

tcol1, tcol2 = st.columns(2)

with tcol1:
    hour_rows = []
    for cid in selected_clusters:
        sub    = viz_sel[viz_sel["cluster"] == cid]["hour"].dropna()
        counts = sub.value_counts().reindex(range(24), fill_value=0)
        for h, c in counts.items():
            hour_rows.append({
                "Hour":    int(h),
                "Trips":   int(c),
                "Segment": label_map[cid],
            })
    hour_df  = pd.DataFrame(hour_rows)
    fig_hour = px.bar(
        hour_df, x="Hour", y="Trips", color="Segment",
        barmode="group",
        color_discrete_map={label_map[cid]: COLORS.get(cid) for cid in cluster_ids},
        title="Trip count by hour of day",
        labels={"Hour": "Hour (24h)", "Trips": "Trips"},
    )
    fig_hour.add_vrect(
        x0=6, x1=9, fillcolor="yellow", opacity=0.08, line_width=0,
        annotation_text="AM rush", annotation_position="top left",
    )
    fig_hour.add_vrect(
        x0=16, x1=19, fillcolor="orange", opacity=0.08, line_width=0,
        annotation_text="PM rush", annotation_position="top left",
    )
    fig_hour.update_layout(height=360, legend=dict(orientation="h", y=-0.28))
    st.plotly_chart(fig_hour, use_container_width=True)

with tcol2:
    dow_map  = {0: "Mon", 1: "Tue", 2: "Wed", 3: "Thu", 4: "Fri", 5: "Sat", 6: "Sun"}
    dow_rows = []
    for cid in selected_clusters:
        sub    = viz_sel[viz_sel["cluster"] == cid]["dow"].dropna()
        counts = sub.value_counts().reindex(range(7), fill_value=0)
        for d, c in counts.items():
            dow_rows.append({
                "Day":     dow_map[int(d)],
                "Trips":   int(c),
                "Segment": label_map[cid],
                "_ord":    int(d),
            })
    dow_df  = pd.DataFrame(dow_rows).sort_values("_ord")
    fig_dow = px.line(
        dow_df, x="Day", y="Trips", color="Segment",
        markers=True,
        color_discrete_map={label_map[cid]: COLORS.get(cid) for cid in cluster_ids},
        title="Trip count by day of week",
        category_orders={"Day": list(dow_map.values())},
    )
    fig_dow.update_layout(height=360, legend=dict(orientation="h", y=-0.28))
    st.plotly_chart(fig_dow, use_container_width=True)

st.markdown("---")

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — ORIGIN–DESTINATION CORRIDORS
# ══════════════════════════════════════════════════════════════════════════════
st.subheader("3. Origin–Destination Corridors")

rg_valid = rg[rg["n_riders"] >= 5].copy()
rg_valid["corridor_label"] = rg_valid["corridor_label"].fillna("Unknown")
rg_valid = rg_valid[~rg_valid["corridor_label"].str.strip().str.startswith("→", na=False)]
rg_valid = rg_valid[rg_valid["corridor_label"] != "Mixed routes"]
# Exclude same-zone corridors (pickup == dropoff zone, format "pid__did")
rg_valid = rg_valid[rg_valid["corridor_id"].apply(
    lambda x: x.split("__")[0] != x.split("__")[1] if "__" in str(x) else True
)]
rg_valid = rg_valid.sort_values("n_riders", ascending=False).reset_index(drop=True)

corridor_options = rg_valid["corridor_label"].tolist()

selected_corridor = st.selectbox(
    "Select corridor (pickup zone → dropoff zone)",
    options=corridor_options,
    format_func=lambda x: (
        f"{x}  ({rg_valid.loc[rg_valid['corridor_label'] == x, 'n_riders'].values[0]:,} riders)"
    ),
)

corridor_row    = rg_valid[rg_valid["corridor_label"] == selected_corridor].iloc[0]
corridor_id     = corridor_row["corridor_id"]
corridor_riders = rp[rp["corridor_id"] == corridor_id].copy().reset_index(drop=True)

# ── Summary metrics ───────────────────────────────────────────────────────────
sc1, sc2, sc3 = st.columns(3)
sc1.metric("Riders on corridor", f"{len(corridor_riders):,}")
sc2.metric("Avg trips / week",   f"{corridor_riders['trips_per_week'].mean():.1f}")
sc3.metric("Peak hour",          f"{int(round(corridor_riders['avg_hour'].mean()))}:00")

st.markdown("")

# ── Load trips for this corridor ──────────────────────────────────────────────
corridor_rider_ids = tuple(sorted(corridor_riders["rider_id"].tolist()))
corridor_trips     = get_corridor_trips(corridor_rider_ids)

r_left, r_right = st.columns([2, 1])

# ── Map: individual pickup (large) + dropoff (small), colour per rider ────────
with r_left:
    st.markdown("**Individual pickup & dropoff points — each colour = one rider**")
    palette     = (px.colors.qualitative.Plotly + px.colors.qualitative.Safe
                   + px.colors.qualitative.Vivid)
    rider_list  = corridor_riders["rider_id"].tolist()[:25]
    rider_color = {rid: palette[i % len(palette)] for i, rid in enumerate(rider_list)}

    map_rows = []
    sub_trips = corridor_trips[corridor_trips["rider_id"].isin(rider_list)]
    for _, t in sub_trips.iterrows():
        for lat, lon, pt, sz in [
            (t["start_lat"], t["start_lon"], "Pickup",  10),
            (t["end_lat"],   t["end_lon"],   "Dropoff",  5),
        ]:
            if pd.notna(lat) and pd.notna(lon):
                zone = (t.get("pickup_zone_name", "") if pt == "Pickup"
                        else t.get("dropoff_zone_name", ""))
                map_rows.append({
                    "rider_id":    t["rider_id"],
                    "lat":         float(lat),
                    "lon":         float(lon),
                    "type":        pt,
                    "marker_size": sz,
                    "zone":        zone,
                })
    map_df = pd.DataFrame(map_rows)

    if not map_df.empty:
        fig_map = px.scatter_map(
            map_df,
            lat="lat", lon="lon",
            color="rider_id",
            size="marker_size",
            hover_data={
                "rider_id":    True,
                "type":        True,
                "zone":        True,
                "lat":         False,
                "lon":         False,
                "marker_size": False,
            },
            zoom=11,
            map_style="carto-positron",
            height=480,
            title=f"{selected_corridor}  (large = pickup, small = dropoff)",
        )
        fig_map.update_layout(
            margin=dict(l=0, r=0, t=40, b=0),
            legend_title_text="Rider",
        )
        st.plotly_chart(fig_map, use_container_width=True)
    else:
        st.info("No mappable trip coordinates for this corridor.")

# ── Rider table ───────────────────────────────────────────────────────────────
with r_right:
    st.markdown("**Riders on this corridor**")

    pii_cols = [c for c in ("full_name", "email", "phone_number", "home_area", "work_area")
                if c in corridor_riders.columns]
    stat_cols = [c for c in ("trips_per_week", "avg_hour", "pct_am_rush", "pct_pm_rush")
                 if c in corridor_riders.columns]
    display = corridor_riders[pii_cols + stat_cols].copy()
    display = display.sort_values("trips_per_week", ascending=False)
    display = display.rename(columns={
        "full_name":     "Full Name",
        "email":         "Email",
        "phone_number":  "Phone",
        "home_area":     "Home Area",
        "work_area":     "Work Area",
        "trips_per_week": "Trips/wk",
        "avg_hour":       "Peak Hour",
        "pct_am_rush":    "AM Rush%",
        "pct_pm_rush":    "PM Rush%",
    })
    if "Trips/wk" in display.columns:
        display["Trips/wk"] = display["Trips/wk"].apply(
            lambda x: int(round(x)) if pd.notna(x) else 0)
    if "Peak Hour" in display.columns:
        display["Peak Hour"] = display["Peak Hour"].apply(
            lambda x: f"{int(round(x))}:00" if pd.notna(x) else "—")
    for col in ("AM Rush%", "PM Rush%"):
        if col in display.columns:
            display[col] = (display[col] * 100).round(0).astype(int).astype(str) + "%"

    st.dataframe(display, use_container_width=True, hide_index=True, height=480)

# ── Per-rider time chart (top 8 by frequency) ─────────────────────────────────
st.markdown("**When each rider travels — top 8 by trip frequency**")
top8 = (corridor_riders
        .sort_values("trips_per_week", ascending=False)
        .head(8)["rider_id"].tolist())
hour_rows2 = []
for rid in top8:
    sub    = corridor_trips[corridor_trips["rider_id"] == rid]["hour"].dropna()
    counts = sub.value_counts().reindex(range(24), fill_value=0)
    for h, c in counts.items():
        hour_rows2.append({"Hour": int(h), "Trips": int(c), "Rider": rid})

if hour_rows2:
    hdf2   = pd.DataFrame(hour_rows2)
    fig_h2 = px.line(
        hdf2, x="Hour", y="Trips", color="Rider",
        markers=True,
        title="Per-rider trip time distribution (top 8 by frequency)",
        labels={"Hour": "Hour of day", "Trips": "Trip count"},
    )
    fig_h2.add_vrect(x0=6,  x1=9,  fillcolor="yellow", opacity=0.08, line_width=0)
    fig_h2.add_vrect(x0=16, x1=19, fillcolor="orange",  opacity=0.08, line_width=0)
    fig_h2.update_layout(height=300, legend=dict(orientation="h", y=-0.4))
    st.plotly_chart(fig_h2, use_container_width=True)

# ── Find similar riders ────────────────────────────────────────────────────────
st.markdown("**Find similar riders**")


def _rider_label(row):
    name = row.get("full_name", "") or ""
    if pd.isna(name):
        name = ""
    name = name.strip()
    return f"{name}  ({row['rider_id']})" if name else row["rider_id"]


corridor_riders["_label"] = corridor_riders.apply(_rider_label, axis=1)

sel_label = st.selectbox(
    "Select a rider to find similar riders",
    options=corridor_riders["_label"].tolist(),
    key="sim_rider_select",
)

sel_rider_id = corridor_riders.loc[
    corridor_riders["_label"] == sel_label, "rider_id"
].values[0]

ref = corridor_riders[corridor_riders["rider_id"] == sel_rider_id].iloc[0]

# Selected rider card
sim_c1, sim_c2 = st.columns([1, 2])
with sim_c1:
    st.markdown(f"""
| Field | Value |
|---|---|
| **Name** | {ref.get('full_name', '—') or '—'} |
| **Email** | {ref.get('email', '—') or '—'} |
| **Phone** | {ref.get('phone_number', '—') or '—'} |
| **Home** | {ref.get('home_area', '—') or '—'} |
| **Work** | {ref.get('work_area', '—') or '—'} |
| **Corridor** | {ref.get('corridor_label', '—')} |
| **Trips/wk** | {int(round(ref['trips_per_week']))} |
| **Peak Hour** | {int(round(ref['avg_hour']))}:00 |
""")

with sim_c2:
    excl_sim = {
        "rider_id", "corridor_id", "corridor_label",
        "pickup_zone_name", "dropoff_zone_name",
        "primary_pickup_zone_id", "primary_dropoff_zone_id",
        "total_completed_trips", "_label",
        "full_name", "email", "phone_number", "home_area", "work_area",
        "cluster", "cluster_label",
    }
    num_feats_corr = [
        c for c in corridor_riders.select_dtypes(include="number").columns
        if c not in excl_sim
    ]

    if len(corridor_riders) > 1 and num_feats_corr:
        X_corr = corridor_riders[num_feats_corr].fillna(0).values
        k      = min(6, len(corridor_riders))
        nbrs   = NearestNeighbors(n_neighbors=k, metric="euclidean").fit(X_corr)
        query  = corridor_riders.loc[
            corridor_riders["rider_id"] == sel_rider_id, num_feats_corr
        ].fillna(0).values
        _, idx = nbrs.kneighbors(query)
        sim_riders = corridor_riders.iloc[idx[0][1:]]

        pii_sim = [c for c in ("full_name", "email", "phone_number", "home_area", "work_area")
                   if c in sim_riders.columns]
        sim_stat_cols = [c for c in ("trips_per_week", "avg_hour", "pct_am_rush", "pct_pm_rush")
                         if c in sim_riders.columns]
        sim_show = sim_riders[pii_sim + sim_stat_cols + ["corridor_label"]].copy()
        sim_show = sim_show.rename(columns={
            "full_name":     "Full Name",
            "email":         "Email",
            "phone_number":  "Phone",
            "home_area":     "Home Area",
            "work_area":     "Work Area",
            "trips_per_week": "Trips/wk",
            "avg_hour":       "Peak Hour",
            "pct_am_rush":    "AM Rush%",
            "pct_pm_rush":    "PM Rush%",
            "corridor_label": "Corridor",
        })
        if "Trips/wk" in sim_show.columns:
            sim_show["Trips/wk"] = sim_show["Trips/wk"].apply(
                lambda x: int(round(x)) if pd.notna(x) else 0)
        if "Peak Hour" in sim_show.columns:
            sim_show["Peak Hour"] = sim_show["Peak Hour"].apply(
                lambda x: f"{int(round(x))}:00" if pd.notna(x) else "—")
        for col in ("AM Rush%", "PM Rush%"):
            if col in sim_show.columns:
                sim_show[col] = (sim_show[col] * 100).round(0).astype(int).astype(str) + "%"

        st.markdown("**Most similar riders on this corridor**")
        st.dataframe(sim_show, use_container_width=True, hide_index=True)
    else:
        st.info("Not enough riders in this corridor for similarity comparison.")

st.markdown("---")

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 4 — RIDER LOOKUP
# ══════════════════════════════════════════════════════════════════════════════
st.subheader("4. Rider Lookup")

rider_input = st.text_input(
    "Paste rider_id",
    placeholder="e.g. 623c9eff40f4ad7de1b6738e",
)

if not rider_input:
    st.info("Paste a rider ID above to see their segment and similar riders.")
elif rider_input not in feat["rider_id"].values:
    st.error(
        f"Rider `{rider_input}` not found.\n\n"
        f"Sample IDs: `{', '.join(feat['rider_id'].sample(3).values)}`"
    )
else:
    r   = feat[feat["rider_id"] == rider_input].iloc[0]
    cid = int(r["cluster"])

    # Get corridor for this rider
    rp_row       = rp[rp["rider_id"] == rider_input]
    corridor_str = rp_row["corridor_label"].values[0] if len(rp_row) > 0 else "—"

    lc, rc = st.columns([1, 2])

    with lc:
        color = COLORS.get(cid, "#6B7280")
        st.markdown(f"""
        <div class="seg-card" style="background:{color}">
          <div class="card-title">{r.get('full_name', '') or rider_input}</div>
          <div class="card-count">{label_map[cid]}</div>
          <div class="card-stats">
            📧 {r.get('email', '—') or '—'}<br>
            📞 {r.get('phone_number', '—') or '—'}<br>
            🏠 {r.get('home_area', '—') or '—'}<br>
            💼 {r.get('work_area', '—') or '—'}<br>
            🛣️ {corridor_str}<br>
            📅 {int(round(r['trips_per_week']))} trips/week<br>
            🕐 Peak: {int(round(r['avg_hour']))}:00
          </div>
        </div>
        """, unsafe_allow_html=True)

    with rc:
        st.markdown(f"**10 most similar riders to** `{rider_input}`")

        excl_lookup = {
            "rider_id", "cluster", "cluster_label",
            "total_trips", "completed_trips", "completion_rate",
            "avg_fare_ngn", "avg_distance_km", "avg_duration_mins",
            "avg_waiting_mins", "pct_cash", "pct_wallet",
            "pct_long_trip", "pct_short_trip", "commute_intensity",
            "pct_is_late_night", "pct_is_midday", "pct_is_evening",
            "full_name", "email", "phone_number", "home_area", "work_area",
        }
        num_cols = [
            c for c in feat.select_dtypes(include="number").columns
            if c not in excl_lookup
        ]

        cluster_feat = feat[feat["cluster"] == cid].copy().reset_index(drop=True)
        X_cluster    = cluster_feat[num_cols].fillna(0).values

        nbrs  = NearestNeighbors(n_neighbors=11, metric="euclidean").fit(X_cluster)
        query = feat.loc[feat["rider_id"] == rider_input, num_cols].fillna(0).values
        _, idx = nbrs.kneighbors(query)
        similar = cluster_feat.iloc[idx[0][1:]].copy()   # skip self

        # Attach corridor info
        similar = similar.merge(rp[["rider_id", "corridor_label"]], on="rider_id", how="left")

        show_cols = (
            [c for c in ("full_name", "email", "phone_number") if c in similar.columns]
            + [c for c in ("trips_per_week", "avg_hour", "pct_is_am_rush", "pct_is_pm_rush")
               if c in similar.columns]
            + (["corridor_label"] if "corridor_label" in similar.columns else [])
        )

        styled = similar[show_cols].rename(columns={
            "full_name":      "Full Name",
            "email":          "Email",
            "phone_number":   "Phone",
            "trips_per_week": "Trips/wk",
            "avg_hour":       "Peak Hour",
            "pct_is_am_rush": "AM Rush%",
            "pct_is_pm_rush": "PM Rush%",
            "corridor_label": "Corridor",
        }).copy()

        if "Trips/wk" in styled.columns:
            styled["Trips/wk"] = styled["Trips/wk"].apply(
                lambda x: int(round(x)) if pd.notna(x) else 0)
        if "Peak Hour" in styled.columns:
            styled["Peak Hour"] = styled["Peak Hour"].apply(
                lambda x: f"{int(round(x))}:00" if pd.notna(x) else "—")
        for col in ("AM Rush%", "PM Rush%"):
            if col in styled.columns:
                styled[col] = (styled[col] * 100).round(0).astype(int).astype(str) + "%"

        st.dataframe(styled, use_container_width=True, hide_index=True)

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("---")
st.caption(
    "Source: 2.5M real trips · 555K users · 252,218 riders clustered "
    "| KMeans (full dataset) | Lagos, Nigeria"
)
