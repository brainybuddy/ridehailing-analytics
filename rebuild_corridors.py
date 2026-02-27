#!/usr/bin/env python3
"""
rebuild_corridors.py
====================
Rebuilds corridor assignments for all riders using MiniBatchKMeans on
raw lat/lon data from full_trips_zones.csv.

Steps:
  1. Load trips, filter to valid lat/lon rows
  2. MiniBatchKMeans(k=50) on pickup (start_lat, start_lon)
  3. Name each zone by most common request_area_name among pickups
  4. Deduplicate names: append N/S/E/W when multiple clusters share a name
  5. Predict dropoff zones for all trips using the same model
  6. Per rider: mode pickup zone = primary_pickup_zone; mode dropoff = primary_dropoff
  7. Corridor = "PrimaryPickup → PrimaryDropoff"; riders with < 2 trips → "Mixed routes"
  8. Write full_user_route_profiles.csv and full_route_groups.csv

Run:
  venv/bin/python3 rebuild_corridors.py
"""

import sys
import numpy as np
import pandas as pd
from collections import defaultdict
from sklearn.cluster import MiniBatchKMeans

DATA_DIR = "/Users/macbook/Documents/ridehailing data"

# ── Step 1: Load trips ────────────────────────────────────────────────────────
print("Step 1: Loading full_trips_zones.csv …")
tz = pd.read_csv(
    f"{DATA_DIR}/full_trips_zones.csv",
    usecols=[
        "rider_id", "hour", "dow",
        "start_lat", "start_lon", "end_lat", "end_lon",
        "request_area_name",
    ],
)

for col in ("start_lat", "start_lon", "end_lat", "end_lon", "hour", "dow"):
    tz[col] = pd.to_numeric(tz[col], errors="coerce")

# Keep only trips with valid pickup coords
valid = tz.dropna(subset=["start_lat", "start_lon"]).copy()
print(f"  {len(valid):,} trips with valid pickup coords (of {len(tz):,} total)")

# ── Step 2: MiniBatchKMeans on pickup coords ──────────────────────────────────
print("Step 2: Fitting MiniBatchKMeans(k=50) on pickup coordinates …")
K = 50
X_pickup = valid[["start_lat", "start_lon"]].values

km = MiniBatchKMeans(n_clusters=K, random_state=42, batch_size=10_000, n_init=5)
km.fit(X_pickup)

valid["pickup_zone_id"] = km.labels_.astype(int)
centroids = km.cluster_centers_   # shape (K, 2): [lat, lon]
print("  Done.")

# ── Step 3: Name each zone by most common request_area_name ──────────────────
print("Step 3: Naming zones by most common request_area_name …")

# Clean display names — maps raw area name → human-readable label
CLEAN_NAMES = {
    "aluasa / oregun /allen":             "Allen / Oregun",
    "ikeja gra / opebi / maryland":       "Ikeja GRA",
    "isheri-olofin / shangisha / magodo": "Magodo",
    "agbotikuyo / dopemu / tabon tabon":  "Agege",
    "anythony / mende / ifako":           "Anthony Village",
    "yaba / sabo yaba":                   "Yaba",
    "idi oro / idi-araba / babalosa":     "Mushin",
    "cms / tbs / lagos island":           "Lagos Island",
    "victoria island - vi":               "Victoria Island",
    "maroko / oniru":                     "Oniru",
    "lekki phase i":                      "Lekki Phase I",
    "jakande / osapa london":             "Jakande",
    "eleganza / ikota":                   "Ikota",
    "ajah / vgc / ado":                   "Ajah",
    "ologolo / agungi":                   "Agungi",
    "igboefon  / chevron":                "Chevron",
    "lekki garden phase  ii iii iv":      "Lekki Gardens",
    "sangotedo - lekki":                  "Sangotedo",
    "lambasa / badore":                   "Badore",
    "lakowe - lekki":                     "Lakowe",
    "ikoyi i / osborne":                  "Ikoyi",
    "amuwo odofin housing estate":        "Amuwo Odofin",
    "isale/idimangoro":                   "Isale Eko",
    "orile / oshodi":                     "Oshodi",
    "itire / ikate / animashaun":         "Surulere",
    "ikotun / egbe":                      "Ikotun",
    "fagba":                              "Fagba",
    "aga / ijimu":                        "Ikorodu South",
    "igbaga aige":                        "Ikorodu",
    "alagbado - alimosho":                "Alimosho",
    "sabo - ojo":                         "Ojo",
}

# For zones whose area name is "Unknown", fall back to coordinate-based name
COORD_FALLBACKS = [
    (6.75, 9.00, 3.00, 4.00, "Sagamu Road"),
    (6.65, 6.75, 3.00, 4.00, "Mowe / Ofada"),
    (6.60, 6.65, 3.45, 4.00, "Ikorodu North"),
]

def _mode_name(s):
    s = s.dropna()
    return s.mode().iloc[0] if len(s) > 0 else "Unknown"

zone_raw_names = (
    valid.groupby("pickup_zone_id")["request_area_name"]
    .agg(_mode_name)
    .to_dict()
)

# Apply clean names (raw → display label)
def _clean(raw_name, zone_id):
    if raw_name != "Unknown":
        key = raw_name.strip().lower()
        return CLEAN_NAMES.get(key, raw_name.strip().title())
    # Unknown → coordinate fallback
    lat, lon = centroids[zone_id][0], centroids[zone_id][1]
    for lat_min, lat_max, lon_min, lon_max, name in COORD_FALLBACKS:
        if lat_min <= lat < lat_max and lon_min <= lon < lon_max:
            return name
    return "Outer Lagos"

zone_display_names = {zid: _clean(raw, zid) for zid, raw in zone_raw_names.items()}

# ── Step 4: Deduplicate names ─────────────────────────────────────────────────
print("Step 4: Deduplicating zone names …")

name_to_clusters = defaultdict(list)
for cid, name in zone_display_names.items():
    name_to_clusters[name].append(cid)

zone_names = {}   # zone_id → human-readable name
for name, cids in name_to_clusters.items():
    if len(cids) == 1:
        zone_names[cids[0]] = name
    else:
        lats = np.array([centroids[c][0] for c in cids])
        lons = np.array([centroids[c][1] for c in cids])
        mid_lat = lats.mean()
        mid_lon = lons.mean()

        used_dirs = {}
        directions = {}
        for cid in cids:
            lat = centroids[cid][0]
            lon = centroids[cid][1]
            dlat = lat - mid_lat
            dlon = lon - mid_lon
            d = ("N" if dlat >= 0 else "S") if abs(dlat) >= abs(dlon) else (
                "E" if dlon >= 0 else "W"
            )
            if d in used_dirs:
                d = str(cid)
            used_dirs[d] = cid
            directions[cid] = d

        for cid in cids:
            zone_names[cid] = f"{name} ({directions[cid]})"

print(f"  {len(zone_names)} zones named")
print("  Sample:", list(zone_names.values())[:8])

# ── Step 5: Predict dropoff zones ────────────────────────────────────────────
print("Step 5: Predicting dropoff zones …")
has_dropoff = valid.dropna(subset=["end_lat", "end_lon"]).copy()
dropoff_zone_arr = km.predict(has_dropoff[["end_lat", "end_lon"]].values)
valid.loc[has_dropoff.index, "dropoff_zone_id"] = dropoff_zone_arr.astype(float)
# rows without end coords stay NaN in dropoff_zone_id
valid["dropoff_zone_id"] = valid["dropoff_zone_id"].where(
    valid[["end_lat", "end_lon"]].notna().all(axis=1)
)
print(f"  Dropoff zones assigned for {has_dropoff.shape[0]:,} trips")

# Add human-readable zone names to the trip rows
valid["pickup_zone_name"]  = valid["pickup_zone_id"].map(zone_names)
valid["dropoff_zone_name"] = valid["dropoff_zone_id"].map(zone_names)

# ── Step 6: Per-rider statistics ──────────────────────────────────────────────
print("Step 6: Computing per-rider statistics …")

# Pre-compute boolean flag columns for efficient aggregation
valid["_is_weekend"]  = valid["dow"] >= 5
valid["_is_am_rush"]  = (valid["hour"] >= 6) & (valid["hour"] < 9)
valid["_is_pm_rush"]  = (valid["hour"] >= 16) & (valid["hour"] < 19)

rider_stats = (
    valid.groupby("rider_id", sort=False)
    .agg(
        total_completed_trips=("rider_id",  "count"),
        avg_pickup_lat        =("start_lat", "mean"),
        avg_pickup_lon        =("start_lon", "mean"),
        avg_dropoff_lat       =("end_lat",   "mean"),
        avg_dropoff_lon       =("end_lon",   "mean"),
        avg_hour              =("hour",      "mean"),
        pct_weekend           =("_is_weekend", "mean"),
        pct_am_rush           =("_is_am_rush",  "mean"),
        pct_pm_rush           =("_is_pm_rush",  "mean"),
    )
    .reset_index()
)

# Primary pickup zone (mode) and consistency
def _primary(s):
    m = s.dropna()
    return int(m.mode().iloc[0]) if len(m) > 0 else -1

def _consistency(s):
    m = s.dropna()
    if len(m) == 0:
        return 0.0
    return float((m == m.mode().iloc[0]).mean())

pickup_grp  = valid.groupby("rider_id", sort=False)["pickup_zone_id"]
pickup_mode = pickup_grp.agg(_primary).rename("primary_pickup_zone_id")
pickup_cons = pickup_grp.agg(_consistency).rename("pickup_consistency")

dropoff_valid = valid.dropna(subset=["dropoff_zone_id"])
dropoff_grp   = dropoff_valid.groupby("rider_id", sort=False)["dropoff_zone_id"]
dropoff_mode  = dropoff_grp.agg(_primary).rename("primary_dropoff_zone_id")
dropoff_cons  = dropoff_grp.agg(_consistency).rename("dropoff_consistency")

rider_stats = (
    rider_stats
    .merge(pickup_mode,  on="rider_id", how="left")
    .merge(pickup_cons,  on="rider_id", how="left")
    .merge(dropoff_mode, on="rider_id", how="left")
    .merge(dropoff_cons, on="rider_id", how="left")
)

rider_stats["primary_pickup_zone_id"]  = rider_stats["primary_pickup_zone_id"].fillna(-1).astype(int)
rider_stats["primary_dropoff_zone_id"] = rider_stats["primary_dropoff_zone_id"].fillna(-1).astype(int)
rider_stats["pickup_consistency"]      = rider_stats["pickup_consistency"].fillna(0.0)
rider_stats["dropoff_consistency"]     = rider_stats["dropoff_consistency"].fillna(0.0)

# Map zone names
rider_stats["pickup_zone_name"]  = rider_stats["primary_pickup_zone_id"].map(zone_names)
rider_stats["dropoff_zone_name"] = rider_stats["primary_dropoff_zone_id"].map(zone_names)

# ── Step 7: Corridor assignment ───────────────────────────────────────────────
print("Step 7: Assigning corridors …")

pid   = rider_stats["primary_pickup_zone_id"]
did   = rider_stats["primary_dropoff_zone_id"]
n_trp = rider_stats["total_completed_trips"]

pname = pid.map(zone_names).fillna("Unknown")
dname = did.map(zone_names).fillna("Unknown")

valid_corr = (n_trp >= 1) & (pid >= 0) & (did >= 0) & (pname != "Unknown") & (dname != "Unknown")

rider_stats["corridor_id"]    = "mixed"
rider_stats["corridor_label"] = "Mixed routes"

rider_stats.loc[valid_corr, "corridor_id"] = (
    pid[valid_corr].astype(str) + "__" + did[valid_corr].astype(str)
)
rider_stats.loc[valid_corr, "corridor_label"] = (
    pname[valid_corr] + " → " + dname[valid_corr]
)

# ── Step 8: Merge cluster info from full_user_features.csv ───────────────────
print("Step 8: Merging cluster info from full_user_features.csv …")
feat = pd.read_csv(
    f"{DATA_DIR}/full_user_features.csv",
    usecols=["rider_id", "cluster", "cluster_label", "trips_per_week"],
)
rider_stats = rider_stats.merge(feat, on="rider_id", how="left")

# ── Step 9: Write full_user_route_profiles.csv ───────────────────────────────
print("Step 9: Writing full_user_route_profiles.csv …")
out_cols = [
    "rider_id", "total_completed_trips",
    "avg_pickup_lat", "avg_pickup_lon", "avg_dropoff_lat", "avg_dropoff_lon",
    "primary_pickup_zone_id", "pickup_consistency",
    "primary_dropoff_zone_id", "dropoff_consistency",
    "avg_hour", "pct_weekend", "pct_am_rush", "pct_pm_rush",
    "pickup_zone_name", "dropoff_zone_name",
    "trips_per_week", "cluster", "cluster_label",
    "corridor_id", "corridor_label",
]
rider_stats[out_cols].to_csv(f"{DATA_DIR}/full_user_route_profiles.csv", index=False)
print(f"  {len(rider_stats):,} riders written to full_user_route_profiles.csv")

# ── Step 10: Write full_route_groups.csv ─────────────────────────────────────
print("Step 10: Writing full_route_groups.csv …")

named = rider_stats[
    (rider_stats["corridor_id"] != "mixed") & rider_stats["corridor_id"].notna()
].copy()

rg = (
    named
    .groupby(["corridor_id", "corridor_label"], sort=False)
    .agg(
        n_riders          =("rider_id",       "count"),
        avg_trips_per_week=("trips_per_week",  "mean"),
        avg_hour          =("avg_hour",        "mean"),
        rider_ids         =("rider_id",        lambda s: ",".join(s.astype(str))),
    )
    .reset_index()
    .sort_values("n_riders", ascending=False)
    .reset_index(drop=True)
)

rg.to_csv(f"{DATA_DIR}/full_route_groups.csv", index=False)
print(f"  {len(rg):,} corridors written to full_route_groups.csv")

# ── Verification ──────────────────────────────────────────────────────────────
print("\n=== Verification ===")
total = len(rider_stats)
named_count = named["rider_id"].nunique()
coverage = named_count / total * 100

print(f"Total riders with trip data : {total:,}")
print(f"Named corridor coverage     : {coverage:.1f}%  ({named_count:,} / {total:,} riders)")
print(f"Unique corridors            : {len(rg):,}")
print(f"\nTop 15 corridors:")
print(rg.head(15)[["corridor_label", "n_riders"]].to_string(index=False))
print("\nDone!")
