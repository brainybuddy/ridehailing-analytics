"""
enrich_pii.py
-------------
Adds home_area and work_area from lagosride.users.export.csv to full_user_pii.csv.
Also regenerates viz_trips.csv with a larger 250K-trip sample for denser map coverage.
"""
import pandas as pd
import numpy as np

# ── 1. Enrich PII ─────────────────────────────────────────────────────────────
print("Enriching PII with home/work areas ...")

pii = pd.read_csv("full_user_pii.csv", dtype=str)
export_cols = ["_id", "home_area", "work_area", "gender"]
export = pd.read_csv("lagosride.users.export.csv", usecols=export_cols, dtype=str)

pii = pii.merge(export.rename(columns={"_id": "rider_id"}), on="rider_id", how="left")

# Normalise home/work area strings
for col in ("home_area", "work_area"):
    pii[col] = pii[col].str.strip().str.title()
    pii[col] = pii[col].where(pii[col].notna() & (pii[col] != "") & (pii[col].str.lower() != "nan"), "")

pii.to_csv("full_user_pii.csv", index=False)

n_home = (pii["home_area"] != "").sum()
n_work = (pii["work_area"] != "").sum()
print(f"  home_area filled: {n_home:,} / {len(pii):,}  ({n_home/len(pii)*100:.0f}%)")
print(f"  work_area filled: {n_work:,} / {len(pii):,}  ({n_work/len(pii)*100:.0f}%)")
print(f"  Saved -> full_user_pii.csv  ({len(pii):,} rows, {len(pii.columns)} columns)")

# ── 2. Larger viz_trips sample ────────────────────────────────────────────────
print("\nRegenerating viz_trips.csv with 250K trips ...")

trips_zones = pd.read_csv("full_trips_zones.csv", dtype=str)
viz = trips_zones.sample(n=min(250_000, len(trips_zones)), random_state=42)
viz.to_csv("viz_trips.csv", index=False)
print(f"  Saved -> viz_trips.csv  ({len(viz):,} rows from {len(trips_zones):,} total)")
print("Done.")
