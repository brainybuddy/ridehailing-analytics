"""
process_full_data.py
--------------------
Full pipeline on all 2.5M trip records and 555K users.

Stages
  1. LOAD    — stream all 14 CSVs in chunks, accumulate per-rider stats
  2. ZONES   — fit DBSCAN on 200K-trip sample, assign all completed trips
               to nearest zone via NearestNeighbors
  3. FEATURES — build per-rider feature matrix
  4. CLUSTER  — KMeans on all riders
  5. ROUTES   — corridor groups from zone assignments
  6. USERS    — pull name/email/phone for all riders from users file
  7. SAVE     — write full_*.csv files used by the dashboard

Outputs
  full_trips_zones.csv        all completed trips with geo-zone labels
  full_user_features.csv      per-rider feature matrix
  full_user_clusters.csv      rider_id + cluster + cluster_label
  full_user_route_profiles.csv per-rider corridor fingerprint
  full_route_groups.csv       corridors with rider lists
  full_user_pii.csv           rider_id + full_name + email + phone
  viz_trips.csv               100K random completed trips for map rendering
"""

import glob
import math
from collections import defaultdict

import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN, KMeans
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler

TRIP_PATTERN = "lagosride.trip_requests.export*.csv"
USERS_FILE   = "lagosride.users.csv"
CHUNK        = 100_000
DBSCAN_SAMPLE = 200_000   # trips used to fit geo zones
VIZ_SAMPLE    = 100_000   # trips saved for dashboard map
EPS_KM        = 0.8
EPS_RAD       = EPS_KM / 6371.0
MIN_SAMPLES   = 10
MIN_COMP      = 0         # include ALL riders with any trip (0 = no minimum)

TRIP_COLS = [
    "rider_id", "ride_status",
    "start_at", "end_at",
    "start_lat", "start_lon",
    "end_lat",   "end_lon",
    "request_lga", "request_area_name",
    "fare", "total_distance", "est_dst",
    "payment_method", "waiting_time",
]

trip_files = sorted(glob.glob(TRIP_PATTERN))
print(f"Files: {len(trip_files)}  |  Chunk: {CHUNK:,}\n")


# ═════════════════════════════════════════════════════════════════════════════
# STAGE 1 — Stream all trips; accumulate per-rider partial sums
# ═════════════════════════════════════════════════════════════════════════════
print("Stage 1: Streaming all trips ...")

# Accumulators (defaultdict so missing keys = 0)
acc = defaultdict(lambda: {
    "n_total": 0, "n_comp": 0,
    "sum_hour": 0.0, "sum_dist": 0.0, "sum_fare": 0.0, "sum_wait": 0.0,
    "sum_dur": 0.0,
    "n_am": 0, "n_pm": 0, "n_late": 0, "n_mid": 0, "n_eve": 0,
    "n_wknd": 0, "n_cash": 0, "n_wallet": 0,
    "n_short": 0, "n_long": 0,
    "first_dt": None, "last_dt": None,
})

# Collect completed trips for zone fitting + viz sample
comp_rows = []
total_streamed = 0

for fp in trip_files:
    for chunk in pd.read_csv(fp, usecols=TRIP_COLS, chunksize=CHUNK,
                              dtype=str, on_bad_lines="skip"):
        total_streamed += len(chunk)

        # Parse numerics
        for c in ("start_lat","start_lon","end_lat","end_lon",
                  "fare","total_distance","est_dst","waiting_time"):
            chunk[c] = pd.to_numeric(chunk[c], errors="coerce")

        chunk["start_at"] = pd.to_datetime(chunk["start_at"], utc=True, errors="coerce")
        chunk["end_at"]   = pd.to_datetime(chunk["end_at"],   utc=True, errors="coerce")
        chunk["hour"]     = chunk["start_at"].dt.hour
        chunk["dow"]      = chunk["start_at"].dt.dayofweek
        chunk["dist"]     = chunk["total_distance"].where(
                                chunk["total_distance"] > 0, chunk["est_dst"])

        chunk["dur"] = (chunk["end_at"] - chunk["start_at"]).dt.total_seconds() / 60
        chunk["dur"] = chunk["dur"].clip(lower=0)

        pm = chunk["payment_method"].str.lower().fillna("")

        for _, r in chunk.iterrows():
            rid = r["rider_id"]
            if not isinstance(rid, str) or not rid:
                continue
            a = acc[rid]
            a["n_total"] += 1
            is_comp = r["ride_status"] == "completed"
            if is_comp:
                a["n_comp"] += 1
                h = r["hour"]
                if pd.notna(h):
                    a["sum_hour"] += h
                    a["n_am"]   += 1 if 6  <= h <= 9  else 0
                    a["n_pm"]   += 1 if 16 <= h <= 19 else 0
                    a["n_late"] += 1 if h >= 23 or h <= 5 else 0
                    a["n_mid"]  += 1 if 10 <= h <= 15 else 0
                    a["n_eve"]  += 1 if 20 <= h <= 22 else 0
                d = r["dow"]
                if pd.notna(d):
                    a["n_wknd"] += 1 if d >= 5 else 0
                dist = r["dist"]
                if pd.notna(dist):
                    a["sum_dist"] += dist
                    a["n_short"] += 1 if dist < 3  else 0
                    a["n_long"]  += 1 if dist > 15 else 0
                fare = r["fare"]
                if pd.notna(fare) and fare > 0:
                    a["sum_fare"] += fare
                wait = r["waiting_time"]
                if pd.notna(wait):
                    a["sum_wait"] += wait
                dur = r["dur"]
                if pd.notna(dur):
                    a["sum_dur"] += dur
                dt = r["start_at"]
                if pd.notna(dt):
                    a["first_dt"] = dt if a["first_dt"] is None else min(a["first_dt"], dt)
                    a["last_dt"]  = dt if a["last_dt"]  is None else max(a["last_dt"],  dt)

            p = str(r["payment_method"]).lower() if pd.notna(r["payment_method"]) else ""
            a["n_cash"]   += 1 if p == "cash"   else 0
            a["n_wallet"] += 1 if "wallet" in p else 0

        # Collect completed trips within Lagos for zones + viz
        comp_chunk = chunk[
            (chunk["ride_status"] == "completed") &
            chunk["start_lat"].between(6.2, 7.0) &
            chunk["start_lon"].between(3.0, 3.8) &
            chunk["end_lat"].between(6.2, 7.0) &
            chunk["end_lon"].between(3.0, 3.8)
        ][["rider_id","start_at","hour","dow",
           "start_lat","start_lon","end_lat","end_lon",
           "request_lga","request_area_name","dist","fare"]]
        comp_rows.append(comp_chunk)

    print(f"  {fp.split('/')[-1]}  —  {total_streamed:,} rows streamed so far")

comp_df = pd.concat(comp_rows, ignore_index=True)
print(f"\n  Total streamed : {total_streamed:,}")
print(f"  Completed (Lagos bbox): {len(comp_df):,}")
print(f"  Unique riders  : {len(acc):,}")


# ═════════════════════════════════════════════════════════════════════════════
# STAGE 2 — Geo-zone clustering (DBSCAN on sample → assign all via kNN)
# ═════════════════════════════════════════════════════════════════════════════
print("\nStage 2: Geo-zone clustering ...")

def fit_and_assign_zones(df, lat_col, lon_col, sample_n=DBSCAN_SAMPLE):
    pts = df[[lat_col, lon_col]].dropna()
    idx = pts.index

    # Fit DBSCAN on a random sample
    sample_idx = np.random.choice(len(pts), size=min(sample_n, len(pts)), replace=False)
    sample_coords = np.radians(pts.iloc[sample_idx].values)

    db = DBSCAN(eps=EPS_RAD, min_samples=MIN_SAMPLES,
                algorithm="ball_tree", metric="haversine")
    sample_labels = db.fit_predict(sample_coords)

    # Centroids of each real cluster (ignore noise -1)
    unique_zones = [z for z in np.unique(sample_labels) if z >= 0]
    centroids = np.array([
        sample_coords[sample_labels == z].mean(axis=0) for z in unique_zones
    ])

    if len(centroids) == 0:
        return pd.Series(-1, index=df.index)

    # Assign all points to nearest centroid
    all_coords = np.radians(pts.values)
    nbrs = NearestNeighbors(n_neighbors=1, algorithm="ball_tree", metric="haversine")
    nbrs.fit(centroids)
    dists, near_idx = nbrs.kneighbors(all_coords)

    # Points too far from any centroid → noise (-1)
    # threshold: 2 km
    threshold_rad = 2.0 / 6371.0
    zone_labels = np.where(dists[:, 0] <= threshold_rad,
                           [unique_zones[i] for i in near_idx[:, 0]],
                           -1)

    result = pd.Series(-1, index=df.index, dtype=int)
    result.loc[idx] = zone_labels
    return result

np.random.seed(42)
print("  Pickup zones ...")
comp_df["pickup_zone_id"]  = fit_and_assign_zones(comp_df, "start_lat", "start_lon")
print(f"    {comp_df['pickup_zone_id'].nunique()-1} zones")

print("  Dropoff zones ...")
comp_df["dropoff_zone_id"] = fit_and_assign_zones(comp_df, "end_lat", "end_lon")
print(f"    {comp_df['dropoff_zone_id'].nunique()-1} zones")


def label_zones(df, zone_col, area_col, lga_col, lat_col, lon_col):
    rows = []
    for zid, grp in df[df[zone_col] >= 0].groupby(zone_col):
        top_lga  = grp[lga_col].mode().iloc[0]  if grp[lga_col].notna().any()  else ""
        top_area = grp[area_col].mode().iloc[0] if grp[area_col].notna().any() else ""
        area_short = top_area.split(" / ")[0].strip().title() if top_area else ""
        label = area_short if area_short else top_lga.replace("-"," ").title()
        rows.append({
            "zone_id":      int(zid),
            "label":        label,
            "centroid_lat": grp[lat_col].mean(),
            "centroid_lon": grp[lon_col].mean(),
            "n_trips":      len(grp),
        })
    return pd.DataFrame(rows).sort_values("n_trips", ascending=False)

pu_labels = label_zones(comp_df,"pickup_zone_id","request_area_name","request_lga","start_lat","start_lon")
do_labels = label_zones(comp_df,"dropoff_zone_id","request_area_name","request_lga","end_lat","end_lon")

pu_map = pu_labels.set_index("zone_id")["label"].to_dict()
do_map = do_labels.set_index("zone_id")["label"].to_dict()

comp_df["pickup_zone_name"]  = comp_df["pickup_zone_id"].map(pu_map).fillna("Unknown")
comp_df["dropoff_zone_name"] = comp_df["dropoff_zone_id"].map(do_map).fillna("Unknown")

comp_df.to_csv("full_trips_zones.csv", index=False)
print(f"  Saved -> full_trips_zones.csv  ({len(comp_df):,} rows)")

# Viz sample for dashboard maps
viz = comp_df.sample(n=min(VIZ_SAMPLE, len(comp_df)), random_state=42)
viz.to_csv("viz_trips.csv", index=False)
print(f"  Saved -> viz_trips.csv  ({len(viz):,} rows)")


# ═════════════════════════════════════════════════════════════════════════════
# STAGE 3 — Build per-rider feature matrix from accumulators
# ═════════════════════════════════════════════════════════════════════════════
print("\nStage 3: Building feature matrix ...")

# Include ALL riders with any trip record
rows = []
for rid, a in acc.items():
    nc = a["n_comp"]
    nt = a["n_total"]
    if nt == 0:
        continue
    nt   = a["n_total"]
    span = max((a["last_dt"] - a["first_dt"]).days, 1) if a["first_dt"] and a["last_dt"] else 1
    weeks = span / 7

    safe_nc = max(nc, 1)   # avoid division by zero for riders with 0 completed trips
    rows.append({
        "rider_id":          rid,
        "total_trips":       nt,
        "completed_trips":   nc,
        "completion_rate":   nc / nt,
        "trips_per_week":    nt / weeks,
        "avg_hour":          a["sum_hour"] / safe_nc,
        "pct_is_am_rush":    a["n_am"]   / safe_nc,
        "pct_is_pm_rush":    a["n_pm"]   / safe_nc,
        "pct_is_late_night": a["n_late"] / safe_nc,
        "pct_is_midday":     a["n_mid"]  / safe_nc,
        "pct_is_evening":    a["n_eve"]  / safe_nc,
        "pct_is_weekend":    a["n_wknd"] / safe_nc,
        "avg_distance_km":   a["sum_dist"] / safe_nc,
        "pct_short_trip":    a["n_short"] / safe_nc,
        "pct_long_trip":     a["n_long"]  / safe_nc,
        "avg_fare_ngn":      a["sum_fare"] / safe_nc,
        "avg_waiting_mins":  (a["sum_wait"] / nt) / 60,
        "avg_duration_mins": a["sum_dur"] / safe_nc,
        "pct_cash":          a["n_cash"]   / nt,
        "pct_wallet":        a["n_wallet"] / nt,
        "commute_intensity": (a["n_am"] + a["n_pm"]) / safe_nc,
    })

feat = pd.DataFrame(rows).reset_index(drop=True)
print(f"  Total riders in feature matrix: {len(feat):,}")


# ═════════════════════════════════════════════════════════════════════════════
# STAGE 4 — KMeans clustering (scales better than KMeans on full data)
# ═════════════════════════════════════════════════════════════════════════════
print("\nStage 4: Clustering riders ...")

excl = {"rider_id"}
num_cols = [c for c in feat.select_dtypes(include="number").columns if c not in excl]
X_raw = feat[num_cols].fillna(0).values
scaler = StandardScaler()
X = scaler.fit_transform(X_raw)

# Silhouette on a subsample to pick k
from sklearn.metrics import silhouette_score
sample_idx = np.random.choice(len(X), size=min(10_000, len(X)), replace=False)
X_sub = X[sample_idx]

best_k, best_s = 3, -1
for k in range(2, 9):
    lbl = KMeans(n_clusters=k, random_state=42, n_init=5).fit_predict(X_sub)
    s   = silhouette_score(X_sub, lbl)
    print(f"  k={k}  silhouette={s:.4f}")
    if s > best_s:
        best_s, best_k = s, k

print(f"  Best k: {best_k}")
km = KMeans(n_clusters=best_k, random_state=42, n_init=10)
feat["cluster"] = km.fit_predict(X)

# Post-process: merge any degenerate cluster (< 1% of riders) into nearest centroid
from sklearn.preprocessing import StandardScaler as _SS
_any_tiny = True
while _any_tiny:
    counts = feat["cluster"].value_counts()
    tiny = counts[counts / len(feat) < 0.01].index.tolist()
    if not tiny:
        _any_tiny = False
        break
    good = [c for c in sorted(feat["cluster"].unique()) if c not in tiny]
    centroids = {c: X[feat["cluster"] == c].mean(axis=0) for c in good}
    for tc in tiny:
        for idx in np.where(feat["cluster"].values == tc)[0]:
            dists = {c: np.linalg.norm(X[idx] - centroids[c]) for c in good}
            feat.at[feat.index[idx], "cluster"] = min(dists, key=dists.get)
    # Remap to contiguous IDs
    old_ids = sorted(feat["cluster"].unique())
    id_map = {old: new for new, old in enumerate(old_ids)}
    feat["cluster"] = feat["cluster"].map(id_map)

def _label(row):
    if row.get("pct_wallet", 0) > 0.40:
        return "Digital/Frequent Rider"
    if row.get("pct_long_trip", 0) > 0.60:
        return "Long-Haul Rider"
    if row.get("pct_short_trip", 0) > 0.40:
        return "Short-Hop Rider"
    if row.get("pct_is_late_night", 0) > 0.20:
        return "Night Rider"
    if row.get("pct_is_weekend", 0) > 0.55:
        return "Weekend Rider"
    if row.get("pct_is_pm_rush", 0) > 0.30 or row.get("pct_is_evening", 0) > 0.10:
        return "Evening Commuter"
    if row.get("commute_intensity", 0) > 0.45:
        return "Morning Commuter"
    if row.get("trips_per_week", 0) < 0.5:
        return "Occasional Rider"
    return "Regular Daytime Rider"

profiles = feat.groupby("cluster")[num_cols].mean()
feat["cluster_label"] = feat["cluster"].map({i: _label(profiles.loc[i]) for i in profiles.index})

feat.to_csv("full_user_features.csv", index=False)
feat[["rider_id","cluster","cluster_label"]].to_csv("full_user_clusters.csv", index=False)
print(f"  Saved -> full_user_features.csv  ({len(feat):,} riders)")
print("  Cluster sizes:")
for cid, cnt in feat["cluster"].value_counts().sort_index().items():
    print(f"    C{cid} {feat[feat['cluster']==cid]['cluster_label'].iloc[0]}: {cnt:,}")


# ═════════════════════════════════════════════════════════════════════════════
# STAGE 5 — Route corridor profiles
# ═════════════════════════════════════════════════════════════════════════════
print("\nStage 5: Building route corridors ...")

grp = comp_df.groupby("rider_id")

def top_zone(s):
    v = s[s >= 0]
    return int(v.mode().iloc[0]) if len(v) > 0 else -1

def zone_consistency(s):
    v = s[s >= 0]
    return round(v.value_counts(normalize=True).iloc[0], 3) if len(v) > 0 else 0.0

rp = pd.DataFrame({
    "total_completed_trips":  grp.size(),
    "avg_pickup_lat":         grp["start_lat"].mean(),
    "avg_pickup_lon":         grp["start_lon"].mean(),
    "avg_dropoff_lat":        grp["end_lat"].mean(),
    "avg_dropoff_lon":        grp["end_lon"].mean(),
    "primary_pickup_zone_id": grp["pickup_zone_id"].apply(top_zone),
    "pickup_consistency":     grp["pickup_zone_id"].apply(zone_consistency),
    "primary_dropoff_zone_id":grp["dropoff_zone_id"].apply(top_zone),
    "dropoff_consistency":    grp["dropoff_zone_id"].apply(zone_consistency),
    "avg_hour":               grp["hour"].mean(),
    "std_hour":               grp["hour"].std().fillna(0),
    "pct_weekend":            grp["dow"].apply(lambda x: (x >= 5).mean()),
    "pct_am_rush":            grp["hour"].apply(lambda x: x.between(6,9).mean()),
    "pct_pm_rush":            grp["hour"].apply(lambda x: x.between(16,19).mean()),
    "avg_fare_ngn":           grp["fare"].mean(),
    "avg_distance_km":        grp["dist"].mean(),
}).reset_index()

rp["pickup_zone_name"]  = rp["primary_pickup_zone_id"].map(pu_map).fillna("Unknown")
rp["dropoff_zone_name"] = rp["primary_dropoff_zone_id"].map(do_map).fillna("Unknown")

# Merge cluster label
rp = rp.merge(feat[["rider_id","cluster","cluster_label","trips_per_week"]], on="rider_id", how="left")

rp["corridor_id"] = rp.apply(
    lambda r: f"{int(r['primary_pickup_zone_id'])}__{int(r['primary_dropoff_zone_id'])}"
    if r["primary_pickup_zone_id"] >= 0 and r["primary_dropoff_zone_id"] >= 0 else "mixed",
    axis=1,
)
rp["corridor_label"] = rp.apply(
    lambda r: f"{r['pickup_zone_name']} → {r['dropoff_zone_name']}"
    if r["corridor_id"] != "mixed" else "Mixed routes",
    axis=1,
)

rp.to_csv("full_user_route_profiles.csv", index=False)
print(f"  Saved -> full_user_route_profiles.csv  ({len(rp):,} riders)")

route_groups = (
    rp[rp["corridor_id"] != "mixed"]
    .groupby(["corridor_id","corridor_label"])
    .agg(
        n_riders=("rider_id","count"),
        avg_trips_per_week=("trips_per_week","mean"),
        avg_hour=("avg_hour","mean"),
        avg_fare_ngn=("avg_fare_ngn","mean"),
        avg_distance_km=("avg_distance_km","mean"),
        rider_ids=("rider_id", lambda x: ",".join(x.values[:500])),  # cap to 500 per group
    )
    .reset_index()
    .sort_values("n_riders", ascending=False)
)
route_groups.to_csv("full_route_groups.csv", index=False)
print(f"  Top corridors:")
print(route_groups.head(10)[["corridor_label","n_riders","avg_trips_per_week","avg_fare_ngn"]].round(2).to_string(index=False))


# ═════════════════════════════════════════════════════════════════════════════
# STAGE 6 — Pull PII for all riders
# ═════════════════════════════════════════════════════════════════════════════
print("\nStage 6: Extracting PII for ALL 555K users ...")

pii_frames = []
for chunk in pd.read_csv(USERS_FILE,
                          usecols=["_id","first_name","last_name","email","phone_number"],
                          chunksize=50_000, dtype=str, on_bad_lines="skip"):
    pii_frames.append(chunk)

pii = pd.concat(pii_frames, ignore_index=True) if pii_frames else pd.DataFrame()
pii["full_name"] = (pii["first_name"].fillna("") + " " + pii["last_name"].fillna("")).str.strip()
pii = pii.rename(columns={"_id":"rider_id"})[["rider_id","full_name","email","phone_number"]]
pii.to_csv("full_user_pii.csv", index=False)
print(f"  Saved -> full_user_pii.csv  ({len(pii):,} matched)")

print("""
=== All outputs ===
  full_trips_zones.csv
  full_user_features.csv
  full_user_clusters.csv
  full_user_route_profiles.csv
  full_route_groups.csv
  full_user_pii.csv
  viz_trips.csv
Done.
""")
