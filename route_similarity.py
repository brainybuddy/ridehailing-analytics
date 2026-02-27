"""
route_similarity.py
-------------------
Step 1: Cluster all pickup and dropoff coordinates into named geo-zones
        using DBSCAN (no need to specify k; finds dense Lagos neighbourhoods).

Step 2: Build a per-user route fingerprint:
          primary pickup zone  + primary dropoff zone  = "corridor"
          e.g. "eti-osa-east → lagos-island"

Step 3: Group users who share the same corridor — these are the people who
        move from the same geo-area to the same geo-area.

Step 4: Within each corridor group compute individual-level stats:
          trips per week, typical hour, fare, consistency score.

Outputs
  trip_zones.csv            trips with pickup_zone_id + dropoff_zone_id
  zone_labels.csv           zone_id → human-readable area label
  user_route_profiles.csv   one row per rider with corridor fingerprint
  route_groups.csv          groups of riders sharing a corridor
"""

import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN

# ── Load sample trips ─────────────────────────────────────────────────────────
print("Loading sample trips ...")
trips = pd.read_csv("sample_trips.csv", dtype=str)
for col in ("start_lat","start_lon","end_lat","end_lon","fare","total_distance","est_dst"):
    trips[col] = pd.to_numeric(trips[col], errors="coerce")
trips["start_at"] = pd.to_datetime(trips["start_at"], utc=True, errors="coerce")
trips["end_at"]   = pd.to_datetime(trips["end_at"],   utc=True, errors="coerce")
trips["hour"]     = trips["start_at"].dt.hour
trips["dow"]      = trips["start_at"].dt.dayofweek
trips["distance_km"] = trips["total_distance"].where(trips["total_distance"] > 0, trips["est_dst"])

# Completed trips only, within Lagos bounding box
comp = trips[trips["ride_status"] == "completed"].copy()
comp = comp.dropna(subset=["start_lat","start_lon","end_lat","end_lon"])
comp = comp[
    comp["start_lat"].between(6.2, 7.0) & comp["start_lon"].between(3.0, 3.8) &
    comp["end_lat"].between(6.2, 7.0)   & comp["end_lon"].between(3.0, 3.8)
].reset_index(drop=True)

print(f"  {len(comp):,} completed trips within Lagos bounds\n")

# ── DBSCAN geo-zone clustering ────────────────────────────────────────────────
# eps = 0.8 km expressed as radians (haversine metric)
EPS_RAD     = 0.8 / 6371.0
MIN_SAMPLES = 8    # at least 8 trips to form a zone


def fit_zones(lats, lons):
    coords = np.radians(np.column_stack([lats, lons]))
    db = DBSCAN(eps=EPS_RAD, min_samples=MIN_SAMPLES,
                algorithm="ball_tree", metric="haversine")
    return db.fit_predict(coords)


print("Clustering pickup coordinates ...")
comp["pickup_zone_id"] = fit_zones(comp["start_lat"].values, comp["start_lon"].values)
n_pu = (comp["pickup_zone_id"] >= 0).sum()
print(f"  {comp['pickup_zone_id'].nunique()-1} pickup zones  "
      f"| {n_pu:,} trips assigned  "
      f"| {len(comp)-n_pu:,} noise")

print("Clustering dropoff coordinates ...")
comp["dropoff_zone_id"] = fit_zones(comp["end_lat"].values, comp["end_lon"].values)
n_do = (comp["dropoff_zone_id"] >= 0).sum()
print(f"  {comp['dropoff_zone_id'].nunique()-1} dropoff zones  "
      f"| {n_do:,} trips assigned  "
      f"| {len(comp)-n_do:,} noise\n")


# ── Name each zone using the most common LGA + area name in that zone ─────────

def label_zones(df, zone_col, area_col, lga_col, lat_col, lon_col):
    """Return a DataFrame: zone_id → label, centroid_lat, centroid_lon."""
    rows = []
    for zid, grp in df[df[zone_col] >= 0].groupby(zone_col):
        top_lga  = grp[lga_col].mode()[0]  if lga_col  in grp and grp[lga_col].notna().any()  else ""
        top_area = grp[area_col].mode()[0] if area_col in grp and grp[area_col].notna().any() else ""
        # Use first part of area name (before " / ")
        area_short = top_area.split(" / ")[0].strip().title() if top_area else ""
        lga_short  = top_lga.replace("-", " ").title() if top_lga else ""
        label = area_short if area_short else lga_short
        rows.append({
            "zone_id":      int(zid),
            "label":        label,
            "lga":          lga_short,
            "centroid_lat": grp[lat_col].mean(),
            "centroid_lon": grp[lon_col].mean(),
            "n_trips":      len(grp),
        })
    return pd.DataFrame(rows).sort_values("n_trips", ascending=False)


pickup_zone_labels  = label_zones(comp, "pickup_zone_id",  "request_area_name", "request_lga",
                                   "start_lat", "start_lon")
dropoff_zone_labels = label_zones(comp, "dropoff_zone_id", "request_area_name", "request_lga",
                                   "end_lat",   "end_lon")

# Merge labels back onto trips
comp = comp.merge(
    pickup_zone_labels[["zone_id","label"]].rename(columns={"zone_id":"pickup_zone_id","label":"pickup_zone_name"}),
    on="pickup_zone_id", how="left"
)
comp = comp.merge(
    dropoff_zone_labels[["zone_id","label"]].rename(columns={"zone_id":"dropoff_zone_id","label":"dropoff_zone_name"}),
    on="dropoff_zone_id", how="left"
)

# Save enriched trips
save_cols = ["_id","rider_id","ride_status",
             "start_at","end_at","hour","dow",
             "start_lat","start_lon","end_lat","end_lon",
             "pickup_zone_id","pickup_zone_name",
             "dropoff_zone_id","dropoff_zone_name",
             "request_lga","request_area_name",
             "distance_km","fare","payment_method"]
comp[[c for c in save_cols if c in comp.columns]].to_csv("trip_zones.csv", index=False)
print("Saved -> trip_zones.csv")

# Save zone labels
pickup_zone_labels["type"]  = "pickup"
dropoff_zone_labels["type"] = "dropoff"
pd.concat([pickup_zone_labels, dropoff_zone_labels], ignore_index=True)\
  .to_csv("zone_labels.csv", index=False)
print("Saved -> zone_labels.csv\n")


# ── Per-user route fingerprint ────────────────────────────────────────────────
print("Building per-user route fingerprints ...")

date_span_days = max((comp["start_at"].max() - comp["start_at"].min()).days, 1)
weeks = date_span_days / 7


def primary_zone(series):
    """Most frequent non-noise zone for a user."""
    v = series[series >= 0]
    return int(v.mode().iloc[0]) if len(v) > 0 else -1


def zone_consistency(series):
    """Fraction of trips at the primary zone (0=scattered, 1=always same spot)."""
    v = series[series >= 0]
    if len(v) == 0:
        return 0.0
    return round(v.value_counts(normalize=True).iloc[0], 3)


grp = comp.groupby("rider_id")

profiles = pd.DataFrame({
    "total_completed_trips"  : grp.size(),
    "trips_per_week"         : grp.size() / weeks,

    "primary_pickup_zone_id" : grp["pickup_zone_id"].apply(primary_zone),
    "pickup_consistency"     : grp["pickup_zone_id"].apply(zone_consistency),

    "primary_dropoff_zone_id": grp["dropoff_zone_id"].apply(primary_zone),
    "dropoff_consistency"    : grp["dropoff_zone_id"].apply(zone_consistency),

    "avg_pickup_lat"         : grp["start_lat"].mean(),
    "avg_pickup_lon"         : grp["start_lon"].mean(),
    "avg_dropoff_lat"        : grp["end_lat"].mean(),
    "avg_dropoff_lon"        : grp["end_lon"].mean(),

    "avg_hour"               : grp["hour"].mean(),
    "std_hour"               : grp["hour"].std().fillna(0),
    "pct_weekend"            : grp["dow"].apply(lambda x: (x >= 5).mean()),
    "pct_am_rush"            : grp["hour"].apply(lambda x: x.between(6, 9).mean()),
    "pct_pm_rush"            : grp["hour"].apply(lambda x: x.between(16, 19).mean()),

    "avg_fare_ngn"           : grp["fare"].mean(),
    "avg_distance_km"        : grp["distance_km"].mean(),
}).reset_index()

# Add human-readable zone names
pu_name_map = pickup_zone_labels.set_index("zone_id")["label"].to_dict()
do_name_map = dropoff_zone_labels.set_index("zone_id")["label"].to_dict()

profiles["pickup_zone_name"]  = profiles["primary_pickup_zone_id"].map(pu_name_map).fillna("Mixed/Unknown")
profiles["dropoff_zone_name"] = profiles["primary_dropoff_zone_id"].map(do_name_map).fillna("Mixed/Unknown")

# Corridor: only assign when both zones are known
profiles["corridor_id"] = profiles.apply(
    lambda r: f"{int(r['primary_pickup_zone_id'])}__{int(r['primary_dropoff_zone_id'])}"
    if r["primary_pickup_zone_id"] >= 0 and r["primary_dropoff_zone_id"] >= 0
    else "mixed",
    axis=1,
)
profiles["corridor_label"] = profiles.apply(
    lambda r: f"{r['pickup_zone_name']} → {r['dropoff_zone_name']}"
    if r["corridor_id"] != "mixed" else "Mixed routes",
    axis=1,
)

profiles.to_csv("user_route_profiles.csv", index=False)
print(f"  {len(profiles):,} rider profiles saved -> user_route_profiles.csv")


# ── Route groups ──────────────────────────────────────────────────────────────
print("\nBuilding route groups ...")

valid = profiles[profiles["corridor_id"] != "mixed"].copy()

route_groups = (
    valid.groupby(["corridor_id","corridor_label"])
    .agg(
        n_riders         =("rider_id",       "count"),
        avg_trips_per_week=("trips_per_week", "mean"),
        avg_hour         =("avg_hour",        "mean"),
        avg_fare_ngn     =("avg_fare_ngn",    "mean"),
        avg_distance_km  =("avg_distance_km", "mean"),
        rider_ids        =("rider_id",        lambda x: ",".join(x.values)),
    )
    .reset_index()
    .sort_values("n_riders", ascending=False)
    .reset_index(drop=True)
)

route_groups.to_csv("route_groups.csv", index=False)
print(f"  {len(route_groups):,} distinct corridors saved -> route_groups.csv")

print(f"\nTop 15 corridors by number of shared riders:")
print(route_groups.head(15)[
    ["corridor_label","n_riders","avg_trips_per_week","avg_hour","avg_fare_ngn","avg_distance_km"]
].round(2).to_string(index=False))
