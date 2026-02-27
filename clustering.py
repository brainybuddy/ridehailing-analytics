"""
clustering.py
-------------
Clusters Lagos ride-hailing users by transit pattern similarity.

Steps
  1. Build feature matrix via feature_engineering.build_pipeline()
  2. Elbow + silhouette sweep to choose best k
  3. Fit final KMeans model
  4. Label and profile each cluster
  5. Visualise: PCA scatter + feature heatmap + hour distribution
  6. Save all outputs

Outputs (CSV)
  user_clusters.csv                  rider_id + cluster + label
  cluster_profiles.csv               mean feature values per cluster
  cluster_archetype_distribution.csv  (if archetype col present)

Outputs (PNG)
  elbow_silhouette.png
  clusters_pca.png
  cluster_heatmap.png
  cluster_hour_distribution.png
"""

import warnings
warnings.filterwarnings('ignore')

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import seaborn as sns
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score

from feature_engineering import build_pipeline

# ── 1. Build features ─────────────────────────────────────────────────────────
print("Building feature matrix ...")
feat, X, scaler, feat_cols = build_pipeline()
print(f"  {len(feat):,} riders  |  {len(feat_cols)} features\n")

# Drop riders whose feature vectors are all-zero (no completed trips at all)
valid = feat['completed_trips'] > 0
feat  = feat[valid].reset_index(drop=True)
X     = X[valid.values].reset_index(drop=True)
print(f"  After removing riders with 0 completed trips: {len(feat):,}\n")

# ── 2. Elbow + silhouette sweep ───────────────────────────────────────────────
K_RANGE = range(2, 11)
inertias, silhouettes = [], []

print("Sweeping k=2..10 ...")
for k in K_RANGE:
    km  = KMeans(n_clusters=k, random_state=42, n_init=10)
    lbl = km.fit_predict(X)
    inertias.append(km.inertia_)
    s = silhouette_score(X, lbl, sample_size=min(5_000, len(feat)), random_state=42)
    silhouettes.append(s)
    print(f"  k={k:2d}  inertia={km.inertia_:>12,.0f}  silhouette={s:.4f}")

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4))
ax1.plot(list(K_RANGE), inertias, 'bo-', lw=2)
ax1.set(title='Elbow Curve', xlabel='k (clusters)', ylabel='Inertia')
ax1.grid(alpha=0.3)
ax2.plot(list(K_RANGE), silhouettes, 'gs-', lw=2)
ax2.axvline(x=int(np.argmax(silhouettes)) + 2, color='r', linestyle='--', alpha=0.6)
ax2.set(title='Silhouette Score', xlabel='k (clusters)', ylabel='Score')
ax2.grid(alpha=0.3)
plt.tight_layout()
plt.savefig('elbow_silhouette.png', dpi=150)
plt.close()
print("\nSaved -> elbow_silhouette.png")

# ── 3. Final model ────────────────────────────────────────────────────────────
K_BEST = int(np.argmax(silhouettes)) + 2
print(f"\nBest k (highest silhouette): {K_BEST}")

km_final = KMeans(n_clusters=K_BEST, random_state=42, n_init=20)
feat['cluster'] = km_final.fit_predict(X)

print("\nCluster sizes:")
for cid, cnt in feat['cluster'].value_counts().sort_index().items():
    print(f"  Cluster {cid}: {cnt:,} riders ({cnt/len(feat)*100:.1f}%)")

# ── 4. Profile + auto-label ───────────────────────────────────────────────────
PROFILE_COLS = [
    # Volume & time
    'trips_per_week', 'completion_rate',
    'avg_distance_km', 'avg_duration_mins', 'avg_fare_ngn',
    'avg_hour', 'std_hour',
    'pct_is_am_rush', 'pct_is_pm_rush', 'pct_is_late_night',
    'pct_is_evening', 'pct_is_weekend',
    'commute_intensity',
    # Geography
    'pickup_lga_entropy', 'pickup_area_entropy',
    'pct_short_trip', 'pct_long_trip',
    # Payment
    'pct_cash', 'pct_card', 'pct_wallet',
    'avg_waiting_mins',
    # Route frequency features
    'pct_route_1', 'pct_route_2', 'pct_route_3',
    'route_concentration', 'n_unique_routes',
    # Time-route features (commute signature)
    'am_rush_dominant_route_pct', 'pm_rush_dominant_route_pct',
    'bidirectional_commute', 'dominant_route_hour_std',
    # Route entropy features
    'route_entropy', 'dropoff_area_entropy', 'route_coverage',
]
# Only keep columns that exist
PROFILE_COLS = [c for c in PROFILE_COLS if c in feat.columns]

profiles = feat.groupby('cluster')[PROFILE_COLS].mean().round(3)

print("\nCluster Profiles (means):")
print(profiles.T.to_string())
profiles.to_csv('cluster_profiles.csv')


def _auto_label(row):
    """Rule-based label — ordered from most distinctive to most generic."""
    # ── Route-based patterns (highest priority for transit similarity) ────────
    # Bidirectional commuter: A→B morning, B→A evening pattern
    if row.get('bidirectional_commute', 0) > 0.7:
        return 'Fixed Commuter (Bidirectional)'

    # Single-corridor rider: one route dominates
    if row.get('pct_route_1', 0) > 0.5:
        # Check if this is during rush hours
        if row.get('commute_intensity', 0) > 0.4:
            return 'Fixed-Route Commuter'
        return 'Single-Corridor Rider'

    # High route concentration with rush hour usage
    if row.get('route_concentration', 0) > 0.6 and row.get('commute_intensity', 0) > 0.35:
        return 'Fixed-Route Commuter'

    # Multi-route explorer: high route diversity
    if row.get('route_entropy', 0) > 2.0:
        return 'Multi-Route Explorer'

    # ── Payment behaviour ─────────────────────────────────────────────────────
    if row.get('pct_wallet', 0) > 0.40:
        return 'Digital/Frequent Rider'

    # ── Trip distance / duration ──────────────────────────────────────────────
    if row.get('pct_long_trip', 0) > 0.60:
        return 'Long-Haul Rider'
    if row.get('pct_short_trip', 0) > 0.40:
        return 'Short-Hop Rider'

    # ── Time of day patterns ──────────────────────────────────────────────────
    if row.get('pct_is_late_night', 0) > 0.20:
        return 'Night Rider'
    if row.get('pct_is_weekend', 0) > 0.55:
        return 'Weekend Rider'
    if row.get('pct_is_pm_rush', 0) > 0.30 or row.get('pct_is_evening', 0) > 0.10:
        return 'Evening Commuter'
    if row.get('commute_intensity', 0) > 0.45:
        return 'Morning Commuter'

    # ── Volume ────────────────────────────────────────────────────────────────
    if row.get('trips_per_week', 0) < 0.5:
        return 'Occasional Rider'

    return 'Regular Daytime Rider'


cluster_labels = {i: _auto_label(profiles.loc[i]) for i in profiles.index}
print("\nAuto-labels:", cluster_labels)
feat['cluster_label'] = feat['cluster'].map(cluster_labels)

# ── 5a. PCA scatter ───────────────────────────────────────────────────────────
pca    = PCA(n_components=2, random_state=42)
coords = pca.fit_transform(X)

fig, ax = plt.subplots(figsize=(11, 7))
palette = cm.tab10(np.linspace(0, 0.9, K_BEST))
for cid, color in enumerate(palette):
    mask  = feat['cluster'] == cid
    label = f"C{cid}: {cluster_labels[cid]}  (n={mask.sum():,})"
    ax.scatter(coords[mask, 0], coords[mask, 1],
               s=10, alpha=0.45, color=color, label=label)
ax.legend(markerscale=3, fontsize=9, loc='best')
ax.set(
    title=f'Lagos Rider Clusters — PCA 2D  (k={K_BEST})',
    xlabel=f'PC1  ({pca.explained_variance_ratio_[0]*100:.1f}% variance)',
    ylabel=f'PC2  ({pca.explained_variance_ratio_[1]*100:.1f}% variance)',
)
ax.grid(alpha=0.2)
plt.tight_layout()
plt.savefig('clusters_pca.png', dpi=150)
plt.close()
print("Saved -> clusters_pca.png")

# ── 5b. Feature heatmap ───────────────────────────────────────────────────────
profiles_z = profiles.apply(lambda c: (c - c.mean()) / (c.std() + 1e-9))
profiles_z.index = [f"C{i} – {cluster_labels[i]}" for i in profiles_z.index]

fig, ax = plt.subplots(figsize=(16, max(4, K_BEST + 1)))
sns.heatmap(
    profiles_z.T,
    annot=True, fmt='.2f', cmap='RdYlGn',
    linewidths=0.4, ax=ax,
    cbar_kws={'label': 'z-score vs. overall mean'},
)
ax.set_title('Transit Pattern Cluster Profiles  (z-scored)', pad=12)
ax.set_xlabel('Cluster')
ax.set_ylabel('Feature')
plt.tight_layout()
plt.savefig('cluster_heatmap.png', dpi=150)
plt.close()
print("Saved -> cluster_heatmap.png")

# ── 5c. Hour-of-day distribution per cluster ──────────────────────────────────
# Re-load trips to plot hour distributions
from feature_engineering import load_data, _parse_trips
trips_raw, _ = load_data()
trips_parsed  = _parse_trips(trips_raw)
trips_parsed  = trips_parsed[trips_parsed['is_completed'] == 1].copy()
trips_parsed  = trips_parsed.merge(
    feat[['rider_id', 'cluster', 'cluster_label']],
    on='rider_id', how='inner',
)

fig, axes = plt.subplots(1, K_BEST, figsize=(4 * K_BEST, 4), sharey=True)
if K_BEST == 1:
    axes = [axes]
for cid, ax in enumerate(axes):
    sub = trips_parsed[trips_parsed['cluster'] == cid]['hour'].dropna()
    ax.hist(sub, bins=24, range=(0, 24), color=cm.tab10(cid / K_BEST),
            edgecolor='white', alpha=0.85)
    ax.set(title=f"C{cid}: {cluster_labels[cid]}\n(n={len(feat[feat['cluster']==cid]):,} riders)",
           xlabel='Hour of day', xlim=(0, 24))
    ax.set_xticks([0, 6, 12, 18, 23])
    ax.grid(axis='y', alpha=0.3)
axes[0].set_ylabel('Trip count')
fig.suptitle('Trip Hour Distribution by Cluster', fontsize=13, y=1.02)
plt.tight_layout()
plt.savefig('cluster_hour_distribution.png', dpi=150, bbox_inches='tight')
plt.close()
print("Saved -> cluster_hour_distribution.png")

# ── 6. Feature importance ─────────────────────────────────────────────────────
centroid_df = pd.DataFrame(km_final.cluster_centers_, columns=feat_cols)
importance  = centroid_df.std().sort_values(ascending=False)
print("\nTop 10 features driving separation (centroid std dev):")
print(importance.head(10).round(4).to_string())

# ── 7. Save results ───────────────────────────────────────────────────────────
feat[['rider_id', 'cluster', 'cluster_label']].to_csv('user_clusters.csv', index=False)
feat.to_csv('user_features_with_clusters.csv', index=False)
profiles.to_csv('cluster_profiles.csv')

print(f"""
=== Output Files ===
  user_clusters.csv                ({len(feat):,} rows)
  user_features_with_clusters.csv  ({len(feat):,} rows, {len(feat.columns)} cols)
  cluster_profiles.csv             ({K_BEST} clusters x {len(PROFILE_COLS)} features)
  elbow_silhouette.png
  clusters_pca.png
  cluster_heatmap.png
  cluster_hour_distribution.png
""")
