"""
Database Setup and Import Script for Neon/Vercel Postgres
With connection keepalive and batch inserts for reliability
"""

import psycopg2
from psycopg2.extras import execute_values
import pandas as pd
from pathlib import Path
import os
import time

# Database connection
DATABASE_URL = os.environ.get('DATABASE_URL',
    'postgresql://neondb_owner:npg_fCtsPZ71AmuK@ep-cold-darkness-abvv50co-pooler.eu-west-2.aws.neon.tech/neondb?sslmode=require'
)

def get_connection():
    """Get a fresh database connection with keepalive settings"""
    return psycopg2.connect(
        DATABASE_URL,
        keepalives=1,
        keepalives_idle=30,
        keepalives_interval=10,
        keepalives_count=5
    )

def create_tables(conn):
    """Create database tables"""
    cursor = conn.cursor()

    # Drop existing tables
    cursor.execute("DROP TABLE IF EXISTS trips CASCADE")
    cursor.execute("DROP TABLE IF EXISTS users CASCADE")

    # Create users table
    cursor.execute("""
        CREATE TABLE users (
            id TEXT PRIMARY KEY,
            name TEXT,
            email TEXT,
            phone TEXT,
            created_at TIMESTAMP
        )
    """)

    # Create trips table
    cursor.execute("""
        CREATE TABLE trips (
            id TEXT PRIMARY KEY,
            rider_id TEXT,
            rider_name TEXT,
            rider_phone TEXT,
            driver_id TEXT,
            driver_name TEXT,
            ride_status TEXT,
            start_address TEXT,
            end_address TEXT,
            start_lat FLOAT,
            start_lon FLOAT,
            end_lat FLOAT,
            end_lon FLOAT,
            request_area_name TEXT,
            request_lga TEXT,
            amount FLOAT,
            fare FLOAT,
            total_distance FLOAT,
            accept_at TIMESTAMP,
            payment_method TEXT,
            hour INTEGER,
            day_of_week TEXT
        )
    """)

    # Create indexes for fast queries
    cursor.execute("CREATE INDEX idx_trips_area ON trips(request_area_name)")
    cursor.execute("CREATE INDEX idx_trips_rider ON trips(rider_id)")
    cursor.execute("CREATE INDEX idx_trips_status ON trips(ride_status)")
    cursor.execute("CREATE INDEX idx_trips_hour ON trips(hour)")

    conn.commit()
    print("✅ Tables created successfully")

def import_users(data_dir=".", batch_size=5000):
    """Import users from CSV files using fast batch inserts with connection reuse"""
    user_files = list(Path(data_dir).glob("lagosride.users*.csv"))
    print(f"Found {len(user_files)} user files")

    total_imported = 0
    conn = get_connection()  # Reuse single connection
    batch_count = 0

    for file in user_files:
        print(f"Importing {file.name}...")
        df = pd.read_csv(file, low_memory=False)

        # Rename columns to match schema
        col_map = {
            '_id': 'id',
            'fullName': 'name',
            'email': 'email',
            'phone': 'phone',
            'createdAt': 'created_at'
        }
        df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})

        # Select only needed columns and dedupe
        cols = ['id', 'name', 'email', 'phone', 'created_at']
        cols = [c for c in cols if c in df.columns]
        df = df[cols].drop_duplicates(subset=['id'])

        # Fill missing columns with None
        for col in ['id', 'name', 'email', 'phone', 'created_at']:
            if col not in df.columns:
                df[col] = None

        # Replace NaN with None for database
        df = df.where(pd.notnull(df), None)

        # Fast batch insert using list of tuples directly
        for i in range(0, len(df), batch_size):
            batch = df.iloc[i:i+batch_size]
            # Convert to list of tuples (much faster than iterrows)
            values = list(batch[['id', 'name', 'email', 'phone', 'created_at']].itertuples(index=False, name=None))

            # Reconnect every 50 batches to prevent stale connections
            batch_count += 1
            if batch_count % 50 == 0:
                try:
                    conn.close()
                except:
                    pass
                time.sleep(0.5)
                conn = get_connection()

            cursor = conn.cursor()
            try:
                execute_values(cursor, """
                    INSERT INTO users (id, name, email, phone, created_at)
                    VALUES %s
                    ON CONFLICT (id) DO NOTHING
                """, values)
                conn.commit()
                print(f"  Progress: {min(i+batch_size, len(df)):,}/{len(df):,} users...")
            except Exception as e:
                print(f"  Error in batch: {e}")
                try:
                    conn.rollback()
                except:
                    pass
                # Reconnect on error
                try:
                    conn.close()
                except:
                    pass
                time.sleep(1)
                conn = get_connection()

        total_imported += len(df)
        print(f"  Imported {len(df):,} users from {file.name}")

    try:
        conn.close()
    except:
        pass

    print(f"✅ Total users imported: {total_imported:,}")

def import_trips(data_dir=".", batch_size=5000):
    """Import trips from CSV files using fast batch inserts with connection reuse"""
    trip_files = sorted(Path(data_dir).glob("lagosride.trip_requests.export*.csv"))
    print(f"Found {len(trip_files)} trip files")

    total_imported = 0
    conn = get_connection()  # Reuse single connection
    batch_count = 0

    for file in trip_files:
        print(f"Importing {file.name}...")

        # Read in chunks for memory efficiency
        for chunk in pd.read_csv(file, chunksize=batch_size, low_memory=False):
            # Process timestamps
            if 'accept_at' in chunk.columns:
                chunk['accept_at'] = pd.to_datetime(chunk['accept_at'], errors='coerce')
                chunk['hour'] = chunk['accept_at'].dt.hour
                chunk['day_of_week'] = chunk['accept_at'].dt.day_name()

            # Rename _id to id
            if '_id' in chunk.columns:
                chunk = chunk.rename(columns={'_id': 'id'})

            # Ensure all columns exist
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

            # Replace NaN with None for database
            chunk = chunk.where(pd.notnull(chunk), None)

            # Convert accept_at to string for postgres (handles NaT)
            def clean_timestamp(val):
                if val is None or pd.isna(val):
                    return None
                return str(val)
            chunk['accept_at'] = chunk['accept_at'].apply(clean_timestamp)

            # Convert hour to int or None
            def clean_hour(val):
                if val is None or pd.isna(val):
                    return None
                try:
                    return int(val)
                except:
                    return None
            chunk['hour'] = chunk['hour'].apply(clean_hour)

            # Convert to list of tuples (fast)
            values = list(chunk[required_cols].itertuples(index=False, name=None))

            # Reconnect every 50 batches to prevent stale connections
            batch_count += 1
            if batch_count % 50 == 0:
                try:
                    conn.close()
                except:
                    pass
                time.sleep(0.5)  # Small delay to let ports recycle
                conn = get_connection()

            cursor = conn.cursor()
            try:
                execute_values(cursor, """
                    INSERT INTO trips (
                        id, rider_id, rider_name, rider_phone,
                        driver_id, driver_name, ride_status,
                        start_address, end_address,
                        start_lat, start_lon, end_lat, end_lon,
                        request_area_name, request_lga,
                        amount, fare, total_distance,
                        accept_at, payment_method, hour, day_of_week
                    ) VALUES %s
                    ON CONFLICT (id) DO NOTHING
                """, values)
                conn.commit()
            except Exception as e:
                print(f"  Error in batch: {e}")
                try:
                    conn.rollback()
                except:
                    pass
                # Reconnect on error
                try:
                    conn.close()
                except:
                    pass
                time.sleep(1)
                conn = get_connection()

            total_imported += len(chunk)
            print(f"  Progress: {total_imported:,} trips imported...")

    try:
        conn.close()
    except:
        pass

    print(f"✅ Total trips imported: {total_imported:,}")

def main():
    print("🔗 Connecting to Neon database...")
    conn = get_connection()

    print("\n📊 Creating tables...")
    create_tables(conn)
    conn.close()

    print("\n👥 Importing users...")
    import_users()

    print("\n🚗 Importing trips...")
    import_trips()

    # Verify counts
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    user_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM trips")
    trip_count = cursor.fetchone()[0]

    print(f"\n✅ Database ready!")
    print(f"   Users: {user_count:,}")
    print(f"   Trips: {trip_count:,}")

    conn.close()

if __name__ == "__main__":
    main()
