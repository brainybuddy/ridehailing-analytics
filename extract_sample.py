"""
extract_sample.py
-----------------
Extracts a sample of 1,000 active riders from the real Lagos ride-hailing
data, along with all their trip records (proportionate to their activity).

Strategy
  Pass 1 — scan every trip file (rider_id + ride_status only) to count
            completed trips per rider. Keeps memory low.
  Pass 2 — stream through all files again and pull every trip row belonging
            to the sampled riders (completed AND cancelled).

Outputs
  sample_trips.csv  — all trips for the 1,000 sampled riders
  sample_users.csv  — matched user records for those riders
"""

import glob
import random
from collections import Counter

import pandas as pd

random.seed(42)

# ── Config ────────────────────────────────────────────────────────────────────
TRIP_PATTERN = 'lagosride.trip_requests.export*.csv'
USERS_FILE   = 'lagosride.users.csv'
N_RIDERS     = 1_000
MIN_TRIPS    = 5          # minimum completed trips to be considered "active"
CHUNK        = 100_000    # rows per chunk

# Columns to keep from trips (drop PII-heavy & irrelevant fields)
TRIP_COLS = [
    '_id', 'rider_id', 'ride_status', 'ride_type',
    'start_at', 'end_at',
    'start_lat', 'start_lon',
    'end_lat',   'end_lon',
    'request_area_name', 'request_lga',
    'total_distance', 'fare', 'amount',
    'payment_method', 'waiting_time',
    'est_dst', 'est_time',
]

# Columns to keep from users
USER_COLS = [
    '_id', 'gender', 'dob',
    'home_area', 'work_area', 'state',
    'user_type', 'status', 'createdAt',
]

trip_files = sorted(glob.glob(TRIP_PATTERN))
print(f"Trip files found : {len(trip_files)}")
print(f"Target riders    : {N_RIDERS:,}  (min {MIN_TRIPS} completed trips)\n")

# ── Pass 1: count completed trips per rider ───────────────────────────────────
print("Pass 1 — counting completed trips per rider ...")
rider_counts: Counter = Counter()

for fp in trip_files:
    for chunk in pd.read_csv(fp, usecols=['rider_id', 'ride_status'],
                              chunksize=CHUNK, dtype=str,
                              on_bad_lines='skip'):
        mask = chunk['ride_status'] == 'completed'
        rider_counts.update(chunk.loc[mask, 'rider_id'].dropna().values)

active_riders = [r for r, c in rider_counts.items() if c >= MIN_TRIPS]
print(f"  Active riders (>={MIN_TRIPS} completed trips): {len(active_riders):,}")

if len(active_riders) < N_RIDERS:
    print(f"  Warning: only {len(active_riders):,} active riders found; "
          f"using all of them.")
    sampled = set(active_riders)
else:
    sampled = set(random.sample(active_riders, N_RIDERS))

print(f"  Sampled {len(sampled):,} riders\n")

# ── Pass 2: extract all trips for sampled riders ──────────────────────────────
print("Pass 2 — extracting trips for sampled riders ...")
frames = []

for fp in trip_files:
    file_frames = []
    for chunk in pd.read_csv(fp, usecols=TRIP_COLS,
                              chunksize=CHUNK, dtype=str,
                              on_bad_lines='skip'):
        hit = chunk[chunk['rider_id'].isin(sampled)]
        if not hit.empty:
            file_frames.append(hit)
    if file_frames:
        frames.append(pd.concat(file_frames, ignore_index=True))
    print(f"  {fp.split('/')[-1]}")

sample_trips = pd.concat(frames, ignore_index=True)
sample_trips.to_csv('sample_trips.csv', index=False)
print(f"\n  -> sample_trips.csv  ({len(sample_trips):,} rows)")

# ── Match user records ────────────────────────────────────────────────────────
print("\nMatching user records ...")
user_frames = []
for chunk in pd.read_csv(USERS_FILE, usecols=USER_COLS,
                          chunksize=CHUNK, dtype=str,
                          on_bad_lines='skip'):
    hit = chunk[chunk['_id'].isin(sampled)]
    if not hit.empty:
        user_frames.append(hit)

sample_users = pd.concat(user_frames, ignore_index=True) if user_frames else pd.DataFrame()
sample_users.to_csv('sample_users.csv', index=False)
print(f"  -> sample_users.csv  ({len(sample_users):,} rows matched)")

# ── Summary ───────────────────────────────────────────────────────────────────
per_rider = sample_trips.groupby('rider_id').size()
status_pct = sample_trips['ride_status'].value_counts(normalize=True).mul(100).round(1)

print(f"""
=== Sample Summary ===
  Riders          : {len(sampled):,}
  Total trips     : {len(sample_trips):,}
  Trips/rider     : {per_rider.mean():.1f} avg  |  {per_rider.min()}–{per_rider.max()} range
  User records    : {len(sample_users):,} matched

  Trip status breakdown:
{status_pct.to_string()}

  Payment methods:
{sample_trips['payment_method'].value_counts().head(5).to_string()}

  Top pickup LGAs:
{sample_trips['request_lga'].value_counts().head(5).to_string()}
""")
