"""
fix_cluster.py
--------------
Post-process full_user_features.csv to remove the degenerate 1-rider cluster.
Reassigns that rider to the nearest valid cluster centroid, then remaps cluster
IDs to be contiguous (0..N-1) and re-derives cluster labels.
Updates full_user_features.csv and full_user_clusters.csv in place.
"""
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

feat = pd.read_csv("full_user_features.csv")

excl = {"rider_id", "cluster", "cluster_label"}
num_cols = [c for c in feat.select_dtypes(include="number").columns if c not in excl]

X_raw = feat[num_cols].fillna(0).values
scaler = StandardScaler()
X = scaler.fit_transform(X_raw)

# ── identify degenerate cluster(s) ────────────────────────────────────────────
counts = feat["cluster"].value_counts()
min_pct = 0.01
tiny_clusters = counts[counts / len(feat) < min_pct].index.tolist()
good_clusters = [c for c in sorted(feat["cluster"].unique()) if c not in tiny_clusters]

print(f"Tiny clusters (< 1%): {tiny_clusters}")
print(f"Good clusters: {good_clusters}")

# ── compute centroids for good clusters ───────────────────────────────────────
centroids = {}
for c in good_clusters:
    mask = feat["cluster"] == c
    centroids[c] = X[mask].mean(axis=0)

# ── reassign tiny cluster members ─────────────────────────────────────────────
for tc in tiny_clusters:
    tiny_idxs = np.where(feat["cluster"] == tc)[0]
    for idx in tiny_idxs:
        rider_vec = X[idx]
        dists = {c: np.linalg.norm(rider_vec - centroids[c]) for c in good_clusters}
        nearest = min(dists, key=dists.get)
        feat.at[feat.index[idx], "cluster"] = nearest
        print(f"  Rider {feat.iloc[idx]['rider_id']} C{tc} -> C{nearest}")

# ── remap cluster IDs to contiguous 0..N-1 ────────────────────────────────────
old_ids = sorted(feat["cluster"].unique())
id_map = {old: new for new, old in enumerate(old_ids)}
feat["cluster"] = feat["cluster"].map(id_map)

print(f"\nCluster remap: {id_map}")

# ── re-derive labels from cluster mean profiles ────────────────────────────────
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
label_for = {i: _label(profiles.loc[i]) for i in profiles.index}
feat["cluster_label"] = feat["cluster"].map(label_for)

# ── print final distribution ───────────────────────────────────────────────────
print("\nFinal cluster distribution:")
for cid, cnt in feat["cluster"].value_counts().sort_index().items():
    lbl = feat[feat["cluster"] == cid]["cluster_label"].iloc[0]
    print(f"  C{cid} {lbl}: {cnt:,}  ({cnt/len(feat)*100:.1f}%)")

# ── save ──────────────────────────────────────────────────────────────────────
feat.to_csv("full_user_features.csv", index=False)
feat[["rider_id", "cluster", "cluster_label"]].to_csv("full_user_clusters.csv", index=False)
print("\nSaved full_user_features.csv and full_user_clusters.csv")
