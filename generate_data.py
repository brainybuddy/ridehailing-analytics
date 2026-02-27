"""
generate_data.py
----------------
Generates synthetic ride-hailing data for NYC.

  • 7,500 users   (adjust N_USERS)
  • 30,000 trips  (adjust N_TRIPS)

Six behavioural archetypes are embedded so the downstream clustering
script has genuine signal to recover.

Outputs
  users.csv  — one row per user
  trips.csv  — one row per trip, sorted by pickup_datetime
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

np.random.seed(42)

# ── Configuration ─────────────────────────────────────────────────────────────
N_USERS    = 7_500
N_TRIPS    = 30_000
START_DATE = datetime(2024, 1, 1)
END_DATE   = datetime(2024, 12, 31)

# NYC zones: (center_lat, center_lon, spread_degrees)
ZONES = {
    'financial_district': (40.7075, -74.0113, 0.015),
    'midtown':            (40.7549, -73.9840, 0.020),
    'upper_east':         (40.7736, -73.9566, 0.018),
    'upper_west':         (40.7870, -73.9754, 0.018),
    'brooklyn_heights':   (40.6960, -73.9930, 0.015),
    'williamsburg':       (40.7081, -73.9571, 0.015),
    'astoria':            (40.7721, -73.9302, 0.015),
    'jfk_airport':        (40.6413, -73.7781, 0.010),
    'laguardia':          (40.7769, -73.8740, 0.010),
    'harlem':             (40.8116, -73.9465, 0.015),
    'lower_east_side':    (40.7157, -73.9863, 0.015),
    'chelsea':            (40.7465, -74.0014, 0.015),
}

ZONE_NAMES  = list(ZONES.keys())
RESIDENTIAL = [
    'upper_east', 'upper_west', 'brooklyn_heights',
    'williamsburg', 'astoria', 'harlem', 'lower_east_side',
]
COMMERCIAL  = ['financial_district', 'midtown', 'chelsea']
AIRPORTS    = ['jfk_airport', 'laguardia']

# Archetype proportions — must sum to 1.0
ARCHETYPES = {
    'morning_commuter': 0.18,   # 7-9am, home → office
    'bidir_commuter':   0.20,   # 7-9am AND 5-7pm both directions
    'night_rider':      0.13,   # 10pm-2am trips
    'weekend_warrior':  0.14,   # mostly Sat/Sun
    'airport_regular':  0.10,   # frequent airport trips
    'occasional':       0.25,   # low frequency, random times
}

# Relative trip frequency weight per archetype
ACTIVITY = {
    'morning_commuter': 1.6,
    'bidir_commuter':   2.8,
    'night_rider':      1.9,
    'weekend_warrior':  1.1,
    'airport_regular':  0.7,
    'occasional':       0.5,
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _jitter(lat, lon, spread):
    """Random point within a circle of radius `spread` degrees."""
    angle = np.random.uniform(0, 2 * np.pi)
    r     = spread * np.sqrt(np.random.uniform(0, 1))
    return lat + r * np.cos(angle), lon + r * np.sin(angle)


def zone_coords(zone_name):
    lat, lon, spread = ZONES[zone_name]
    return _jitter(lat, lon, spread)


def haversine(lat1, lon1, lat2, lon2):
    """Great-circle distance in km."""
    R    = 6_371.0
    phi1 = np.radians(lat1)
    phi2 = np.radians(lat2)
    a    = (np.sin(np.radians(lat2 - lat1) / 2) ** 2
            + np.cos(phi1) * np.cos(phi2)
            * np.sin(np.radians(lon2 - lon1) / 2) ** 2)
    return 2 * R * np.arcsin(np.sqrt(a))


# ── User generation ───────────────────────────────────────────────────────────

def generate_users():
    archetypes = list(ARCHETYPES.keys())
    probs      = list(ARCHETYPES.values())
    assigned   = np.random.choice(archetypes, size=N_USERS, p=probs)

    rows = []
    for i, archetype in enumerate(assigned):
        home_zone    = np.random.choice(RESIDENTIAL)
        h_lat, h_lon = zone_coords(home_zone)
        days_back    = int(np.random.uniform(30, 730))
        signup       = START_DATE - timedelta(days=days_back)
        rows.append({
            'user_id':    f'U{i+1:05d}',
            'age':        int(np.clip(np.random.normal(34, 10), 18, 75)),
            'gender':     np.random.choice(['M', 'F', 'NB'], p=[0.48, 0.48, 0.04]),
            'signup_date': signup.date(),
            'home_zone':  home_zone,
            'home_lat':   round(h_lat, 6),
            'home_lon':   round(h_lon, 6),
            'archetype':  archetype,
        })
    return pd.DataFrame(rows)


# ── Trip generation helpers ───────────────────────────────────────────────────

def _pickup_hour(archetype, is_weekend):
    if archetype == 'morning_commuter':
        mu = 10 if is_weekend else 8
        return int(np.clip(np.random.normal(mu, 1.0), 6, 13))

    if archetype == 'bidir_commuter':
        if is_weekend:
            return int(np.random.uniform(9, 20))
        if np.random.rand() < 0.55:           # morning leg
            return int(np.clip(np.random.normal(8, 0.8), 6, 10))
        return     int(np.clip(np.random.normal(18, 0.8), 16, 21))  # evening leg

    if archetype == 'night_rider':
        return int(np.clip(np.random.normal(24, 1.8), 21, 27)) % 24

    if archetype == 'weekend_warrior':
        return int(np.random.uniform(10, 23) if is_weekend else np.random.uniform(8, 22))

    if archetype == 'airport_regular':
        return int(np.random.uniform(5, 22))

    # occasional
    return int(np.random.uniform(7, 22))


def _route(archetype, home_zone):
    if archetype == 'morning_commuter':
        return home_zone, np.random.choice(COMMERCIAL)

    if archetype == 'bidir_commuter':
        if np.random.rand() < 0.55:
            return home_zone, np.random.choice(COMMERCIAL)
        return np.random.choice(COMMERCIAL), home_zone

    if archetype == 'airport_regular':
        if np.random.rand() < 0.5:
            return home_zone, np.random.choice(AIRPORTS)
        return np.random.choice(AIRPORTS), home_zone

    if archetype == 'night_rider':
        non_res = [z for z in ZONE_NAMES if z not in RESIDENTIAL + AIRPORTS]
        return np.random.choice(non_res), np.random.choice(ZONE_NAMES)

    return np.random.choice(ZONE_NAMES), np.random.choice(ZONE_NAMES)


# ── Trip generation ───────────────────────────────────────────────────────────

def generate_trips(users):
    user_dict = users.set_index('user_id').to_dict('index')

    # Weight sampling so high-activity archetypes appear more
    weights = np.array(
        [ACTIVITY[user_dict[uid]['archetype']] for uid in users['user_id']]
    )
    weights /= weights.sum()
    sampled_uids = np.random.choice(users['user_id'].values,
                                    size=N_TRIPS, p=weights)

    date_span = (END_DATE - START_DATE).days
    rows = []
    for i, uid in enumerate(sampled_uids):
        info      = user_dict[uid]
        day_off   = int(np.random.uniform(0, date_span))
        trip_date = START_DATE + timedelta(days=day_off)
        is_wknd   = trip_date.weekday() >= 5

        hour      = _pickup_hour(info['archetype'], is_wknd)
        minute    = int(np.random.uniform(0, 60))
        pickup_dt = trip_date.replace(hour=hour % 24, minute=minute, second=0)

        pu_zone, do_zone = _route(info['archetype'], info['home_zone'])
        pu_lat,  pu_lon  = zone_coords(pu_zone)
        do_lat,  do_lon  = zone_coords(do_zone)

        dist_km  = haversine(pu_lat, pu_lon, do_lat, do_lon)
        # duration: proportional to distance + noise
        duration = max(3.0, dist_km * 3.5 + float(np.random.normal(5, 2.5)))
        dropoff_dt = pickup_dt + timedelta(minutes=duration)

        fare = round(
            max(3.0, 2.50 + dist_km * 1.80 + duration * 0.40
                + float(np.random.normal(0, 1.5))),
            2,
        )

        rows.append({
            'trip_id':          f'T{i+1:06d}',
            'user_id':          uid,
            'pickup_zone':      pu_zone,
            'dropoff_zone':     do_zone,
            'pickup_lat':       round(pu_lat, 6),
            'pickup_lon':       round(pu_lon, 6),
            'dropoff_lat':      round(do_lat, 6),
            'dropoff_lon':      round(do_lon, 6),
            'pickup_datetime':  pickup_dt,
            'dropoff_datetime': dropoff_dt,
            'duration_mins':    round(duration, 1),
            'distance_km':      round(dist_km, 2),
            'fare_usd':         fare,
            'is_weekend':       is_wknd,
        })

    return (pd.DataFrame(rows)
              .sort_values('pickup_datetime')
              .reset_index(drop=True))


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print(f"Generating {N_USERS:,} users ...")
    users = generate_users()
    users.to_csv('users.csv', index=False)
    print(f"  -> users.csv  ({len(users):,} rows)")
    print(f"\n  Archetype breakdown:")
    for arch, cnt in users['archetype'].value_counts().items():
        print(f"    {arch:<20s} {cnt:,}  ({cnt/len(users)*100:.1f}%)")

    print(f"\nGenerating {N_TRIPS:,} trips ...")
    trips = generate_trips(users)
    trips.to_csv('trips.csv', index=False)
    print(f"  -> trips.csv  ({len(trips):,} rows)")
    print(f"\n  Date range : {trips['pickup_datetime'].min().date()}"
          f" to {trips['pickup_datetime'].max().date()}")
    print(f"  Trips/user : {len(trips)/len(users):.1f} avg  "
          f"(range {trips.groupby('user_id').size().min()}–"
          f"{trips.groupby('user_id').size().max()})")
    print(f"  Weekend %  : {trips['is_weekend'].mean()*100:.1f}%")
    print(f"  Avg fare   : ${trips['fare_usd'].mean():.2f}")
    print(f"\nSample trips:")
    print(trips[['trip_id','user_id','pickup_zone','dropoff_zone',
                 'pickup_datetime','distance_km','fare_usd']].head(6).to_string(index=False))
