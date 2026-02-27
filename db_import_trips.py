"""
Import trips only - uses COPY for fast bulk loading
Does NOT recreate tables - appends to existing data
"""

import psycopg2
from io import StringIO
import pandas as pd
from pathlib import Path
import os
import time

DATABASE_URL = os.environ.get('DATABASE_URL',
    'postgresql://neondb_owner:npg_fCtsPZ71AmuK@ep-cold-darkness-abvv50co-pooler.eu-west-2.aws.neon.tech/neondb?sslmode=require'
)

def get_connection():
    return psycopg2.connect(
        DATABASE_URL,
        connect_timeout=30,
        keepalives=1,
        keepalives_idle=30,
        keepalives_interval=10,
        keepalives_count=5
    )

def import_trips_copy(data_dir=".", batch_size=50000):
    """Import trips using COPY command for maximum speed"""
    trip_files = sorted(Path(data_dir).glob("lagosride.trip_requests.export*.csv"))
    print(f"Found {len(trip_files)} trip files")

    conn = get_connection()
    cursor = conn.cursor()

    total_imported = 0

    for file in trip_files:
        print(f"\nImporting {file.name}...")

        for chunk in pd.read_csv(file, chunksize=batch_size, low_memory=False):
            # Process timestamps
            if 'accept_at' in chunk.columns:
                chunk['accept_at'] = pd.to_datetime(chunk['accept_at'], errors='coerce')
                chunk['hour'] = chunk['accept_at'].dt.hour
                chunk['day_of_week'] = chunk['accept_at'].dt.day_name()

            # Rename _id to id
            if '_id' in chunk.columns:
                chunk = chunk.rename(columns={'_id': 'id'})

            # Select and order columns
            required_cols = ['id', 'rider_id', 'rider_name', 'rider_phone',
                           'driver_id', 'driver_name', 'ride_status',
                           'start_address', 'end_address',
                           'start_lat', 'start_lon', 'end_lat', 'end_lon',
                           'request_area_name', 'request_lga',
                           'amount', 'fare', 'total_distance',
                           'accept_at', 'payment_method', 'hour', 'day_of_week']

            for col in required_cols:
                if col not in chunk.columns:
                    chunk[col] = None

            # Create temp table for this batch
            cursor.execute("""
                CREATE TEMP TABLE IF NOT EXISTS trips_staging (LIKE trips INCLUDING DEFAULTS)
                ON COMMIT DELETE ROWS
            """)

            # Prepare data for COPY
            output = StringIO()
            chunk[required_cols].to_csv(output, sep='\t', header=False, index=False, na_rep='\\N')
            output.seek(0)

            max_retries = 3
            for retry in range(max_retries):
                try:
                    # COPY to staging table
                    cursor.copy_from(output, 'trips_staging', null='\\N', columns=required_cols)

                    # Insert from staging to main table (skip duplicates)
                    cursor.execute("""
                        INSERT INTO trips
                        SELECT * FROM trips_staging
                        ON CONFLICT (id) DO NOTHING
                    """)

                    conn.commit()
                    total_imported += len(chunk)
                    print(f"  Progress: {total_imported:,} trips processed...")
                    break  # Success, exit retry loop

                except Exception as e:
                    print(f"  Error (attempt {retry+1}/{max_retries}): {e}")
                    # Reconnect
                    try:
                        conn.rollback()
                    except:
                        pass
                    try:
                        conn.close()
                    except:
                        pass

                    if retry < max_retries - 1:
                        print(f"  Waiting 5 seconds before retry...")
                        time.sleep(5)
                        conn = get_connection()
                        cursor = conn.cursor()
                        # Recreate staging table
                        cursor.execute("""
                            CREATE TEMP TABLE IF NOT EXISTS trips_staging (LIKE trips INCLUDING DEFAULTS)
                            ON COMMIT DELETE ROWS
                        """)
                        # Reset StringIO position for retry
                        output.seek(0)
                    else:
                        print(f"  Skipping batch after {max_retries} failed attempts")
                        conn = get_connection()
                        cursor = conn.cursor()
                        total_imported += len(chunk)  # Count as processed even if failed

    conn.close()
    print(f"\n✅ Total trips processed: {total_imported:,}")

if __name__ == "__main__":
    print("🚗 Importing trips to Neon database...")
    print("Note: This appends to existing data, does not recreate tables")
    import_trips_copy()

    # Verify
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM trips")
    print(f"\n📊 Total trips in database: {cursor.fetchone()[0]:,}")
    conn.close()
