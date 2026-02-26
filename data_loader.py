"""
Data Loader Module for Lagos Ride Hailing Data
Efficiently loads and combines trip requests and user data
"""

import pandas as pd
import dask.dataframe as dd
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')


class RideDataLoader:
    """Handles loading and caching of ride-hailing datasets"""

    def __init__(self, data_dir="."):
        self.data_dir = Path(data_dir)
        self.trips_df = None
        self.users_df = None

    def load_trip_requests(self, use_dask=True, sample_frac=None):
        """
        Load all trip request CSV files

        Args:
            use_dask: Use dask for parallel loading (faster for large files)
            sample_frac: Load only a fraction of data (e.g., 0.1 for 10%)

        Returns:
            pandas DataFrame with all trip requests
        """
        trip_files = sorted(self.data_dir.glob("lagosride.trip_requests.export*.csv"))

        if not trip_files:
            raise FileNotFoundError("No trip request files found")

        print(f"Loading {len(trip_files)} trip request files...")

        if use_dask:
            # Use dask for parallel loading
            ddf = dd.read_csv(
                trip_files,
                dtype={
                    'driver_phone': 'object',
                    'rider_phone': 'object',
                    'phone_number': 'object',
                    'vehicle_id': 'object'
                },
                assume_missing=True
            )

            if sample_frac:
                ddf = ddf.sample(frac=sample_frac)

            self.trips_df = ddf.compute()
        else:
            # Traditional pandas loading
            dfs = []
            for file in trip_files:
                df = pd.read_csv(file, dtype={'driver_phone': 'object', 'rider_phone': 'object', 'vehicle_id': 'object'})
                dfs.append(df)

            self.trips_df = pd.concat(dfs, ignore_index=True)

            if sample_frac:
                self.trips_df = self.trips_df.sample(frac=sample_frac)

        # Convert date columns
        date_columns = ['accept_at', 'arrived_at', 'start_at', 'end_at', 'charge_at', 'settlement_at']
        for col in date_columns:
            if col in self.trips_df.columns:
                self.trips_df[col] = pd.to_datetime(self.trips_df[col], errors='coerce')

        # Extract numeric values from fare columns
        if 'est_fare' in self.trips_df.columns:
            self.trips_df['est_fare_min'] = self.trips_df['est_fare'].str.extract(r'N([\d,]+)')[0].str.replace(',', '').astype(float)
            self.trips_df['est_fare_max'] = self.trips_df['est_fare'].str.extract(r'N[\d,]+-N([\d,]+)')[0].str.replace(',', '').astype(float)

        print(f"Loaded {len(self.trips_df):,} trip records")
        return self.trips_df

    def load_users(self):
        """
        Load user data (combines both user CSV files)

        Returns:
            pandas DataFrame with user information
        """
        user_files = list(self.data_dir.glob("lagosride.users*.csv"))

        if not user_files:
            raise FileNotFoundError("No user files found")

        print(f"Loading {len(user_files)} user files...")

        dfs = []
        for file in user_files:
            df = pd.read_csv(
                file,
                dtype={
                    'phone_number': 'object',
                    'work_phone_number': 'object',
                    'contact_person.phone_number': 'object',
                    'referrer.phone_number': 'object'
                }
            )
            dfs.append(df)

        self.users_df = pd.concat(dfs, ignore_index=True).drop_duplicates(subset=['_id'])

        # Convert date columns
        if 'createdAt' in self.users_df.columns:
            self.users_df['createdAt'] = pd.to_datetime(self.users_df['createdAt'], errors='coerce')

        if 'dob' in self.users_df.columns:
            self.users_df['dob'] = pd.to_datetime(self.users_df['dob'], errors='coerce')

        print(f"Loaded {len(self.users_df):,} unique users")
        return self.users_df

    def load_all(self, use_dask=True, sample_frac=None):
        """
        Load both trips and users data

        Args:
            use_dask: Use dask for trip loading
            sample_frac: Sample fraction for trips data

        Returns:
            tuple: (trips_df, users_df)
        """
        trips = self.load_trip_requests(use_dask=use_dask, sample_frac=sample_frac)
        users = self.load_users()
        return trips, users

    def get_data_summary(self):
        """Get summary statistics about loaded data"""
        summary = {}

        if self.trips_df is not None:
            summary['trips'] = {
                'total_records': len(self.trips_df),
                'date_range': (
                    self.trips_df['accept_at'].min(),
                    self.trips_df['accept_at'].max()
                ) if 'accept_at' in self.trips_df.columns else None,
                'unique_drivers': self.trips_df['driver_id'].nunique() if 'driver_id' in self.trips_df.columns else 0,
                'unique_riders': self.trips_df['rider_id'].nunique() if 'rider_id' in self.trips_df.columns else 0,
                'memory_usage_mb': self.trips_df.memory_usage(deep=True).sum() / 1024**2
            }

        if self.users_df is not None:
            summary['users'] = {
                'total_users': len(self.users_df),
                'riders': len(self.users_df[self.users_df['user_type'].str.contains('rider', na=False)]) if 'user_type' in self.users_df.columns else 0,
                'drivers': len(self.users_df[self.users_df['user_type'].str.contains('driver|partner', na=False)]) if 'user_type' in self.users_df.columns else 0,
                'memory_usage_mb': self.users_df.memory_usage(deep=True).sum() / 1024**2
            }

        return summary


if __name__ == "__main__":
    # Test the data loader
    loader = RideDataLoader()
    trips, users = loader.load_all(sample_frac=0.1)  # Load 10% sample for testing

    print("\n" + "="*50)
    print("DATA SUMMARY")
    print("="*50)

    summary = loader.get_data_summary()

    for dataset, stats in summary.items():
        print(f"\n{dataset.upper()}:")
        for key, value in stats.items():
            print(f"  {key}: {value}")
