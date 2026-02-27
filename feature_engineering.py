"""
feature_engineering.py
-----------------------
Joins sample_trips + sample_users and engineers per-rider feature vectors
for transit-pattern clustering.

Feature groups
  1. Volume       — total_trips, completed_trips, completion_rate, trips_per_week
  2. Time-of-day  — pct_am_rush, pct_pm_rush, pct_late_night, pct_midday,
                    pct_evening, avg_hour, std_hour (routine vs. random)
  3. Day-of-week  — pct_weekend, pct_monday–pct_friday (commute signal)
  4. Geography    — pickup_lga_entropy, avg_distance_km, pct_short_trip,
                    pct_long_trip, pct_same_lga
  5. Finance      — avg_fare_ngn, pct_cash, pct_card, pct_wallet
  6. Behaviour    — avg_waiting_secs, avg_trip_duration_mins
  7. Route        — Route-based transit pattern features:
       Frequency  — pct_route_1/2/3, route_concentration, n_unique_routes
       Commute    — am/pm_rush_dominant_route_pct, bidirectional_commute,
                    dominant_route_hour_std
       Entropy    — route_entropy, dropoff_area_entropy, route_coverage

Run standalone:
  python feature_engineering.py

Or import into clustering.py:
  from feature_engineering import build_pipeline
"""

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

# ── Loaders ───────────────────────────────────────────────────────────────────

def load_data(trips_path='sample_trips.csv', users_path='sample_users.csv'):
    trips = pd.read_csv(trips_path, dtype=str)
    users = pd.read_csv(users_path, dtype=str)
    return trips, users


def _parse_trips(trips: pd.DataFrame) -> pd.DataFrame:
    """Clean types; derive temporal columns."""
    t = trips.copy()

    # Datetimes
    t['start_at'] = pd.to_datetime(t['start_at'], utc=True, errors='coerce')
    t['end_at']   = pd.to_datetime(t['end_at'],   utc=True, errors='coerce')

    # Numerics
    for col in ('start_lat', 'start_lon', 'end_lat', 'end_lon',
                'total_distance', 'fare', 'amount', 'waiting_time', 'est_dst'):
        t[col] = pd.to_numeric(t[col], errors='coerce')

    # Derived
    t['duration_mins'] = (t['end_at'] - t['start_at']).dt.total_seconds() / 60
    t['duration_mins'] = t['duration_mins'].clip(lower=0)

    # Use total_distance where available, else est_dst
    t['distance_km'] = t['total_distance'].where(t['total_distance'] > 0, t['est_dst'])

    # Temporal features
    t['hour'] = t['start_at'].dt.hour
    t['dow']  = t['start_at'].dt.dayofweek   # 0=Mon … 6=Sun

    # Time-of-day buckets (Lagos business hours)
    t['is_am_rush']       = t['hour'].between(6,  9).astype(int)
    t['is_midday']        = t['hour'].between(10, 15).astype(int)
    t['is_pm_rush']       = t['hour'].between(16, 19).astype(int)
    t['is_evening']       = t['hour'].between(20, 22).astype(int)
    t['is_late_night']    = ((t['hour'] >= 23) | (t['hour'] <= 5)).astype(int)
    t['is_weekend']       = (t['dow'] >= 5).astype(int)

    # Status flags
    t['is_completed'] = (t['ride_status'] == 'completed').astype(int)
    t['is_cancelled'] = (t['ride_status'] == 'cancel').astype(int)

    # Payment flags
    pm = t['payment_method'].str.lower().fillna('unknown')
    t['pay_cash']   = (pm == 'cash').astype(int)
    t['pay_card']   = pm.str.contains('card', na=False).astype(int)
    t['pay_wallet'] = pm.str.contains('wallet', na=False).astype(int)

    # Short / long trip flags
    t['is_short_trip'] = (t['distance_km'] < 3).astype(int)
    t['is_long_trip']  = (t['distance_km'] > 15).astype(int)

    return t


def _zone_entropy(series: pd.Series) -> float:
    """Shannon entropy of location distribution.
    Low  → predictable/routine routes.
    High → diverse, exploratory travel.
    """
    p = series.value_counts(normalize=True).values
    return float(-np.sum(p * np.log(p + 1e-9)))


# ── Route Feature Functions ───────────────────────────────────────────────────

def _assign_dropoff_zones(trips: pd.DataFrame, grid_size: float = 0.01) -> pd.DataFrame:
    """Bin end_lat/end_lon into grid cells (~1.1km in Lagos).

    Args:
        trips: DataFrame with end_lat, end_lon columns
        grid_size: Grid cell size in degrees (0.01 ≈ 1.1km)

    Returns:
        DataFrame with added 'end_zone' column
    """
    t = trips.copy()
    # Create grid-based zone identifiers for dropoff locations
    t['end_lat_bin'] = (t['end_lat'] / grid_size).round().astype('Int64')
    t['end_lon_bin'] = (t['end_lon'] / grid_size).round().astype('Int64')
    t['end_zone'] = t['end_lat_bin'].astype(str) + '_' + t['end_lon_bin'].astype(str)
    # Clean up nulls
    t.loc[t['end_lat'].isna() | t['end_lon'].isna(), 'end_zone'] = None
    return t


def _build_route_pairs(trips: pd.DataFrame) -> pd.DataFrame:
    """Create 'request_area_name → end_zone' route identifiers.

    Args:
        trips: DataFrame with request_area_name and end_zone columns

    Returns:
        DataFrame with added 'route' column
    """
    t = trips.copy()
    # Create route as "pickup_area → dropoff_zone"
    pickup = t['request_area_name'].fillna('unknown')
    dropoff = t['end_zone'].fillna('unknown')
    t['route'] = pickup + ' → ' + dropoff
    return t


def _build_route_frequency_features(trips: pd.DataFrame, top_n: int = 3) -> pd.DataFrame:
    """Top-N route percentages + concentration metrics.

    Features created:
        - pct_route_1, pct_route_2, pct_route_3: % of trips on top N routes
        - route_concentration: Herfindahl index (high = few routes dominate)
        - n_unique_routes: Total distinct routes taken

    Args:
        trips: DataFrame with rider_id and route columns
        top_n: Number of top routes to track percentages for

    Returns:
        DataFrame indexed by rider_id with route frequency features
    """
    grp = trips.groupby('rider_id')

    def _route_stats(df):
        route_counts = df['route'].value_counts()
        total = len(df)
        n_routes = len(route_counts)

        # Top N route percentages
        top_pcts = []
        for i in range(top_n):
            if i < n_routes:
                top_pcts.append(route_counts.iloc[i] / total)
            else:
                top_pcts.append(0.0)

        # Herfindahl index (sum of squared shares)
        shares = route_counts / total
        herfindahl = float((shares ** 2).sum())

        return pd.Series({
            **{f'pct_route_{i+1}': top_pcts[i] for i in range(top_n)},
            'route_concentration': herfindahl,
            'n_unique_routes': n_routes,
        })

    return grp.apply(_route_stats, include_groups=False).reset_index()


def _build_time_route_features(trips: pd.DataFrame) -> pd.DataFrame:
    """Commute signature: rush hour route patterns + bidirectional detection.

    Features created:
        - am_rush_dominant_route_pct: % of AM rush trips on dominant route
        - pm_rush_dominant_route_pct: % of PM rush trips on dominant route
        - bidirectional_commute: Score for A→B morning / B→A evening pattern
        - dominant_route_hour_std: Timing consistency on dominant route

    Args:
        trips: DataFrame with rider_id, route, hour, is_am_rush, is_pm_rush columns

    Returns:
        DataFrame indexed by rider_id with time-route features
    """
    grp = trips.groupby('rider_id')

    def _commute_stats(df):
        # Find dominant route overall
        route_counts = df['route'].value_counts()
        if len(route_counts) == 0:
            return pd.Series({
                'am_rush_dominant_route_pct': 0.0,
                'pm_rush_dominant_route_pct': 0.0,
                'bidirectional_commute': 0.0,
                'dominant_route_hour_std': 0.0,
            })

        dominant_route = route_counts.index[0]

        # AM rush dominant route percentage
        am_trips = df[df['is_am_rush'] == 1]
        if len(am_trips) > 0:
            am_dom_pct = (am_trips['route'] == dominant_route).mean()
        else:
            am_dom_pct = 0.0

        # PM rush dominant route percentage
        pm_trips = df[df['is_pm_rush'] == 1]
        if len(pm_trips) > 0:
            pm_dom_pct = (pm_trips['route'] == dominant_route).mean()
        else:
            pm_dom_pct = 0.0

        # Bidirectional commute detection (A→B morning, B→A evening)
        bidirectional_score = 0.0
        if len(am_trips) > 0 and len(pm_trips) > 0:
            # Get top AM route
            am_route_counts = am_trips['route'].value_counts()
            top_am_route = am_route_counts.index[0] if len(am_route_counts) > 0 else None

            # Get top PM route
            pm_route_counts = pm_trips['route'].value_counts()
            top_pm_route = pm_route_counts.index[0] if len(pm_route_counts) > 0 else None

            if top_am_route and top_pm_route and top_am_route != top_pm_route:
                # Check if routes are reverse of each other
                # Parse route format: "pickup → dropoff"
                try:
                    am_parts = top_am_route.split(' → ')
                    pm_parts = top_pm_route.split(' → ')
                    if len(am_parts) == 2 and len(pm_parts) == 2:
                        # Check if AM pickup = PM dropoff and AM dropoff = PM pickup
                        if am_parts[0] == pm_parts[1] and am_parts[1] == pm_parts[0]:
                            # Perfect bidirectional match
                            am_top_pct = am_route_counts.iloc[0] / len(am_trips)
                            pm_top_pct = pm_route_counts.iloc[0] / len(pm_trips)
                            bidirectional_score = (am_top_pct + pm_top_pct) / 2
                except:
                    pass

        # Timing consistency on dominant route
        dom_trips = df[df['route'] == dominant_route]
        dom_hour_std = dom_trips['hour'].std() if len(dom_trips) > 1 else 0.0

        return pd.Series({
            'am_rush_dominant_route_pct': am_dom_pct,
            'pm_rush_dominant_route_pct': pm_dom_pct,
            'bidirectional_commute': bidirectional_score,
            'dominant_route_hour_std': dom_hour_std if not pd.isna(dom_hour_std) else 0.0,
        })

    return grp.apply(_commute_stats, include_groups=False).reset_index()


def _build_route_entropy_features(trips: pd.DataFrame) -> pd.DataFrame:
    """Route diversity metrics.

    Features created:
        - route_entropy: Shannon entropy of route distribution
        - dropoff_area_entropy: Diversity of destination zones
        - route_coverage: Fraction of possible zone pairs used

    Args:
        trips: DataFrame with rider_id, route, end_zone, request_area_name columns

    Returns:
        DataFrame indexed by rider_id with route entropy features
    """
    grp = trips.groupby('rider_id')

    def _entropy_stats(df):
        # Route entropy
        route_entropy = _zone_entropy(df['route'])

        # Dropoff area entropy
        dropoff_entropy = _zone_entropy(df['end_zone'].dropna())

        # Route coverage: unique routes / (unique pickups × unique dropoffs)
        n_unique_pickups = df['request_area_name'].nunique()
        n_unique_dropoffs = df['end_zone'].nunique()
        n_unique_routes = df['route'].nunique()
        max_possible_routes = n_unique_pickups * n_unique_dropoffs
        route_coverage = n_unique_routes / max_possible_routes if max_possible_routes > 0 else 0.0

        return pd.Series({
            'route_entropy': route_entropy,
            'dropoff_area_entropy': dropoff_entropy,
            'route_coverage': route_coverage,
        })

    return grp.apply(_entropy_stats, include_groups=False).reset_index()


def build_route_features(trips: pd.DataFrame, top_n: int = 3) -> pd.DataFrame:
    """Orchestrate all route feature building.

    This function:
        1. Assigns dropoff zones to trips
        2. Creates route pairs (pickup → dropoff)
        3. Builds route frequency features
        4. Builds time-route correlation features
        5. Builds route entropy features

    Args:
        trips: Parsed trips DataFrame (output of _parse_trips)
        top_n: Number of top routes to track for frequency features

    Returns:
        DataFrame indexed by rider_id with all route features (13 total)
    """
    # Only use completed trips for route analysis
    comp = trips[trips['is_completed'] == 1].copy()

    # Step 1: Assign dropoff zones
    comp = _assign_dropoff_zones(comp)

    # Step 2: Create route pairs
    comp = _build_route_pairs(comp)

    # Step 3-5: Build feature sets
    freq_feat = _build_route_frequency_features(comp, top_n=top_n)
    time_feat = _build_time_route_features(comp)
    entropy_feat = _build_route_entropy_features(comp)

    # Merge all route features
    route_features = freq_feat.merge(time_feat, on='rider_id', how='outer')
    route_features = route_features.merge(entropy_feat, on='rider_id', how='outer')

    return route_features


# ── Join ──────────────────────────────────────────────────────────────────────

def join_tables(trips: pd.DataFrame, users: pd.DataFrame) -> pd.DataFrame:
    """Left-join trips → users on rider_id / _id."""
    keep = ['_id', 'gender', 'home_area', 'work_area', 'state']
    keep = [c for c in keep if c in users.columns]
    return trips.merge(
        users[keep].rename(columns={'_id': 'rider_id'}),
        on='rider_id',
        how='left',
    )


# ── Feature engineering ───────────────────────────────────────────────────────

def build_features(trips: pd.DataFrame, users: pd.DataFrame) -> pd.DataFrame:
    t   = _parse_trips(trips)
    t   = join_tables(t, users)
    grp = t.groupby('rider_id')

    # ── Volume ────────────────────────────────────────────────────────────────
    feat = pd.DataFrame({
        'total_trips'     : grp.size(),
        'completed_trips' : grp['is_completed'].sum(),
    })
    feat['completion_rate'] = feat['completed_trips'] / feat['total_trips']

    # Date span for each rider (trips per week)
    date_span = grp['start_at'].apply(
        lambda s: max((s.max() - s.min()).days, 1)
    )
    feat['trips_per_week'] = feat['total_trips'] / (date_span / 7).clip(lower=1)

    # ── Time-of-day (on completed trips only) ─────────────────────────────────
    comp = t[t['is_completed'] == 1]
    cgrp = comp.groupby('rider_id')

    for col in ('is_am_rush', 'is_midday', 'is_pm_rush',
                'is_evening', 'is_late_night', 'is_weekend'):
        feat[f'pct_{col}'] = cgrp[col].mean()

    feat['avg_hour'] = cgrp['hour'].mean()
    feat['std_hour'] = cgrp['hour'].std().fillna(0)

    # ── Geography ─────────────────────────────────────────────────────────────
    feat['pickup_lga_entropy']  = cgrp['request_lga'].apply(_zone_entropy)
    feat['pickup_area_entropy'] = cgrp['request_area_name'].apply(_zone_entropy)

    feat['avg_distance_km']  = cgrp['distance_km'].mean()
    feat['std_distance_km']  = cgrp['distance_km'].std().fillna(0)
    feat['pct_short_trip']   = cgrp['is_short_trip'].mean()
    feat['pct_long_trip']    = cgrp['is_long_trip'].mean()

    # ── Finance ───────────────────────────────────────────────────────────────
    feat['avg_fare_ngn'] = cgrp['fare'].mean()
    feat['pct_cash']     = grp['pay_cash'].mean()
    feat['pct_card']     = grp['pay_card'].mean()
    feat['pct_wallet']   = grp['pay_wallet'].mean()

    # ── Behaviour ─────────────────────────────────────────────────────────────
    feat['avg_waiting_mins']    = grp['waiting_time'].mean() / 60   # seconds→mins
    feat['avg_duration_mins']   = cgrp['duration_mins'].mean()

    # Commute intensity: combined am + pm rush share
    feat['commute_intensity'] = (
        feat['pct_is_am_rush'].fillna(0) + feat['pct_is_pm_rush'].fillna(0)
    )

    feat = feat.reset_index()

    # ── Route Features ────────────────────────────────────────────────────────
    route_feat = build_route_features(t, top_n=3)
    feat = feat.merge(route_feat, on='rider_id', how='left')

    # Fill NaN route features with sensible defaults
    route_cols = [
        'pct_route_1', 'pct_route_2', 'pct_route_3',
        'route_concentration', 'n_unique_routes',
        'am_rush_dominant_route_pct', 'pm_rush_dominant_route_pct',
        'bidirectional_commute', 'dominant_route_hour_std',
        'route_entropy', 'dropoff_area_entropy', 'route_coverage',
    ]
    for col in route_cols:
        if col in feat.columns:
            feat[col] = feat[col].fillna(0)

    return feat


def scale_features(
    feat: pd.DataFrame,
    exclude: tuple = ('rider_id', 'total_trips', 'completed_trips'),
) -> tuple:
    """Returns (X_scaled_df, fitted_scaler, feature_col_names)."""
    cols   = [c for c in feat.select_dtypes(include='number').columns
              if c not in exclude]
    scaler = StandardScaler()
    X      = scaler.fit_transform(feat[cols].fillna(0))
    return pd.DataFrame(X, columns=cols, index=feat.index), scaler, cols


def build_pipeline(trips_path='sample_trips.csv', users_path='sample_users.csv'):
    """Full pipeline: load → join → engineer → scale."""
    trips, users = load_data(trips_path, users_path)
    feat         = build_features(trips, users)
    X, scaler, cols = scale_features(feat)
    return feat, X, scaler, cols


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print("Loading sample data ...")
    trips, users = load_data()
    print(f"  Trips : {len(trips):,}   Users : {len(users):,}")

    print("\nBuilding features ...")
    feat = build_features(trips, users)
    feat.to_csv('user_features.csv', index=False)
    print(f"  Feature matrix : {feat.shape}  -> user_features.csv")

    print("\nFeature summary:")
    numeric = feat.select_dtypes(include='number')
    print(numeric.describe().T[['mean', 'std', 'min', 'max']].round(3).to_string())

    # Quick sanity: riders with no completed trips (edge case)
    zeros = (feat['completed_trips'] == 0).sum()
    if zeros:
        print(f"\n  Note: {zeros} riders have 0 completed trips "
              f"(all rows are cancellations for them).")
