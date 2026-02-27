"""
Database Data Loader for Neon/Vercel Postgres
Replaces CSV-based loading with database queries
"""

import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor
import os
import streamlit as st

# Database connection - check Streamlit secrets first, then env var
def get_database_url():
    # Try Streamlit secrets first (for Streamlit Cloud)
    try:
        return st.secrets["DATABASE_URL"]
    except:
        pass
    # Fall back to environment variable
    return os.environ.get('DATABASE_URL',
        'postgresql://neondb_owner:npg_fCtsPZ71AmuK@ep-cold-darkness-abvv50co-pooler.eu-west-2.aws.neon.tech/neondb?sslmode=require'
    )

DATABASE_URL = get_database_url()


class DatabaseLoader:
    """Load data from Neon/Vercel Postgres database"""

    def __init__(self):
        self.conn = None

    def get_connection(self):
        """Get database connection"""
        if self.conn is None or self.conn.closed:
            self.conn = psycopg2.connect(DATABASE_URL)
        return self.conn

    def load_trips(self, sample_frac=None, limit=None):
        """Load trips from database"""
        conn = self.get_connection()

        query = """
            SELECT
                id as _id,
                rider_id, rider_name, rider_phone,
                driver_id, driver_name, ride_status,
                start_address, end_address,
                start_lat, start_lon, end_lat, end_lon,
                request_area_name, request_lga,
                amount, fare, total_distance,
                accept_at, payment_method, hour, day_of_week
            FROM trips
        """

        if sample_frac and sample_frac < 1.0:
            # Use TABLESAMPLE for random sampling
            query = f"""
                SELECT
                    id as _id,
                    rider_id, rider_name, rider_phone,
                    driver_id, driver_name, ride_status,
                    start_address, end_address,
                    start_lat, start_lon, end_lat, end_lon,
                    request_area_name, request_lga,
                    amount, fare, total_distance,
                    accept_at, payment_method, hour, day_of_week
                FROM trips
                TABLESAMPLE BERNOULLI({sample_frac * 100})
            """
        elif limit:
            query += f" LIMIT {limit}"

        df = pd.read_sql(query, conn)

        # Convert accept_at to datetime if needed
        if 'accept_at' in df.columns:
            df['accept_at'] = pd.to_datetime(df['accept_at'], errors='coerce')

        return df

    def load_users(self):
        """Load users from database"""
        conn = self.get_connection()

        query = """
            SELECT
                id as _id,
                name, email, phone, created_at
            FROM users
        """

        df = pd.read_sql(query, conn)
        return df

    def load_all(self, sample_frac=None):
        """Load both trips and users"""
        trips = self.load_trips(sample_frac=sample_frac)
        users = self.load_users()
        return trips, users

    def get_trip_count(self):
        """Get total trip count"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM trips")
        return cursor.fetchone()[0]

    def get_user_count(self):
        """Get total user count"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        return cursor.fetchone()[0]

    def close(self):
        """Close database connection"""
        if self.conn and not self.conn.closed:
            self.conn.close()


# Cached version for Streamlit
@st.cache_resource
def get_db_loader():
    """Get cached database loader"""
    return DatabaseLoader()


@st.cache_data(show_spinner=False)
def load_data_from_db(sample_frac=None):
    """Load data from database with caching"""
    loader = get_db_loader()
    trips, users = loader.load_all(sample_frac=sample_frac)
    return trips, users


# For backwards compatibility
class RideDataLoader:
    """Wrapper for backwards compatibility with existing code"""

    def __init__(self):
        self.db_loader = DatabaseLoader()

    def load_all(self, use_dask=False, sample_frac=None):
        """Load all data (use_dask ignored for database)"""
        return self.db_loader.load_all(sample_frac=sample_frac)


if __name__ == "__main__":
    # Test the loader
    loader = DatabaseLoader()

    print(f"Total trips: {loader.get_trip_count():,}")
    print(f"Total users: {loader.get_user_count():,}")

    print("\nLoading sample (10%)...")
    trips, users = loader.load_all(sample_frac=0.1)
    print(f"Loaded {len(trips):,} trips, {len(users):,} users")

    loader.close()
