"""
Analytics Module for Lagos Ride Hailing Data
Provides comprehensive analytics across all business dimensions
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from scipy import stats
import warnings
warnings.filterwarnings('ignore')


class RideAnalytics:
    """Comprehensive analytics engine for ride-hailing data"""

    def __init__(self, trips_df, users_df=None):
        self.trips = trips_df.copy()
        self.users = users_df.copy() if users_df is not None else None
        self._preprocess_data()

    def _preprocess_data(self):
        """Preprocess data for analytics"""
        # Add derived columns
        if 'accept_at' in self.trips.columns:
            self.trips['date'] = pd.to_datetime(self.trips['accept_at']).dt.date
            self.trips['hour'] = pd.to_datetime(self.trips['accept_at']).dt.hour
            self.trips['day_of_week'] = pd.to_datetime(self.trips['accept_at']).dt.day_name()
            self.trips['month'] = pd.to_datetime(self.trips['accept_at']).dt.to_period('M')
            self.trips['week'] = pd.to_datetime(self.trips['accept_at']).dt.to_period('W')

        # Clean numeric columns
        if 'amount' in self.trips.columns:
            self.trips['amount'] = pd.to_numeric(self.trips['amount'], errors='coerce')
        if 'fare' in self.trips.columns:
            self.trips['fare'] = pd.to_numeric(self.trips['fare'], errors='coerce')
        if 'total_distance' in self.trips.columns:
            self.trips['total_distance'] = pd.to_numeric(self.trips['total_distance'], errors='coerce')

    # =============================================
    # TRIP ANALYTICS
    # =============================================

    def get_trip_overview(self):
        """Get high-level trip statistics"""
        total_trips = len(self.trips)
        completed = len(self.trips[self.trips['ride_status'] == 'completed'])
        cancelled = len(self.trips[self.trips['ride_status'] == 'cancel'])

        return {
            'total_trips': total_trips,
            'completed_trips': completed,
            'cancelled_trips': cancelled,
            'completion_rate': (completed / total_trips * 100) if total_trips > 0 else 0,
            'cancellation_rate': (cancelled / total_trips * 100) if total_trips > 0 else 0,
            'unique_drivers': self.trips['driver_id'].nunique(),
            'unique_riders': self.trips['rider_id'].nunique(),
            'avg_trips_per_day': self.trips.groupby('date').size().mean() if 'date' in self.trips.columns else 0
        }

    def get_trip_trends(self, freq='D'):
        """
        Get trip volume trends over time

        Args:
            freq: Frequency - 'D' (daily), 'W' (weekly), 'M' (monthly)

        Returns:
            DataFrame with trip counts by time period and status
        """
        if 'accept_at' not in self.trips.columns:
            return pd.DataFrame()

        trips_with_date = self.trips.dropna(subset=['accept_at'])

        trends = trips_with_date.groupby([
            pd.Grouper(key='accept_at', freq=freq),
            'ride_status'
        ]).size().unstack(fill_value=0)

        return trends

    def get_peak_hours(self):
        """Identify peak hours for ride requests"""
        if 'hour' not in self.trips.columns:
            return pd.DataFrame()

        hourly = self.trips.groupby('hour').agg({
            '_id': 'count',
            'ride_status': lambda x: (x == 'completed').sum()
        }).rename(columns={'_id': 'total_requests', 'ride_status': 'completed'})

        hourly['completion_rate'] = (hourly['completed'] / hourly['total_requests'] * 100)

        return hourly.sort_values('total_requests', ascending=False)

    def get_popular_routes(self, top_n=20):
        """Get most popular routes"""
        routes = self.trips.groupby(['start_address', 'end_address']).agg({
            '_id': 'count',
            'total_distance': 'mean',
            'amount': 'mean'
        }).rename(columns={
            '_id': 'trip_count',
            'total_distance': 'avg_distance',
            'amount': 'avg_fare'
        }).sort_values('trip_count', ascending=False)

        return routes.head(top_n)

    def get_cancellation_analysis(self):
        """Analyze cancellation patterns"""
        cancelled = self.trips[self.trips['ride_status'] == 'cancel']

        if len(cancelled) == 0:
            return {}

        return {
            'total_cancelled': len(cancelled),
            'by_hour': cancelled.groupby('hour').size().to_dict() if 'hour' in cancelled.columns else {},
            'by_day': cancelled.groupby('day_of_week').size().to_dict() if 'day_of_week' in cancelled.columns else {},
            'by_area': cancelled.groupby('request_area_name').size().head(10).to_dict() if 'request_area_name' in cancelled.columns else {},
            'avg_waiting_time': cancelled['waiting_time'].mean() if 'waiting_time' in cancelled.columns else 0
        }

    # =============================================
    # FINANCIAL METRICS
    # =============================================

    def get_revenue_overview(self):
        """Get overall revenue statistics"""
        completed = self.trips[self.trips['ride_status'] == 'completed']

        return {
            'total_revenue': completed['amount'].sum(),
            'total_fares': completed['fare'].sum(),
            'avg_fare_per_trip': completed['fare'].mean(),
            'median_fare': completed['fare'].median(),
            'total_outstanding': self.trips['outstanding'].sum() if 'outstanding' in self.trips.columns else 0,
            'revenue_per_km': (completed['fare'].sum() / completed['total_distance'].sum()) if completed['total_distance'].sum() > 0 else 0
        }

    def get_revenue_trends(self, freq='D'):
        """Get revenue trends over time"""
        completed = self.trips[self.trips['ride_status'] == 'completed'].copy()

        if 'accept_at' not in completed.columns:
            return pd.DataFrame()

        revenue_trends = completed.groupby(pd.Grouper(key='accept_at', freq=freq)).agg({
            'amount': 'sum',
            'fare': 'sum',
            '_id': 'count'
        }).rename(columns={'_id': 'trip_count'})

        revenue_trends['avg_fare'] = revenue_trends['fare'] / revenue_trends['trip_count']

        return revenue_trends

    def get_payment_analysis(self):
        """Analyze payment methods"""
        payment_dist = self.trips.groupby('payment_method').agg({
            '_id': 'count',
            'amount': 'sum'
        }).rename(columns={'_id': 'count', 'amount': 'total_amount'})

        return payment_dist

    def get_fare_distribution(self):
        """Get fare distribution statistics"""
        completed = self.trips[self.trips['ride_status'] == 'completed']
        fares = completed['fare'].dropna()

        if len(fares) == 0:
            return {}

        return {
            'min': fares.min(),
            'max': fares.max(),
            'mean': fares.mean(),
            'median': fares.median(),
            'std': fares.std(),
            'percentiles': {
                '25th': fares.quantile(0.25),
                '50th': fares.quantile(0.50),
                '75th': fares.quantile(0.75),
                '90th': fares.quantile(0.90),
                '95th': fares.quantile(0.95)
            }
        }

    # =============================================
    # DRIVER/RIDER BEHAVIOR ANALYTICS
    # =============================================

    def get_driver_performance(self, top_n=50):
        """Analyze driver performance metrics"""
        driver_stats = self.trips.groupby(['driver_id', 'driver_name']).agg({
            '_id': 'count',
            'ride_status': lambda x: (x == 'completed').sum(),
            'amount': 'sum',
            'total_distance': 'sum',
            'waiting_time': 'mean'
        }).rename(columns={
            '_id': 'total_trips',
            'ride_status': 'completed_trips',
            'amount': 'total_revenue',
            'total_distance': 'total_distance_km',
            'waiting_time': 'avg_waiting_time'
        })

        driver_stats['completion_rate'] = (driver_stats['completed_trips'] / driver_stats['total_trips'] * 100)
        driver_stats['avg_revenue_per_trip'] = driver_stats['total_revenue'] / driver_stats['total_trips']

        return driver_stats.sort_values('total_trips', ascending=False).head(top_n)

    def get_rider_behavior(self, top_n=50):
        """Analyze rider behavior patterns"""
        rider_stats = self.trips.groupby(['rider_id', 'rider_name']).agg({
            '_id': 'count',
            'ride_status': lambda x: (x == 'completed').sum(),
            'amount': 'sum',
            'payment_method': lambda x: x.mode()[0] if len(x) > 0 else None
        }).rename(columns={
            '_id': 'total_trips',
            'ride_status': 'completed_trips',
            'amount': 'total_spent',
            'payment_method': 'preferred_payment'
        })

        rider_stats['avg_spend_per_trip'] = rider_stats['total_spent'] / rider_stats['total_trips']
        rider_stats['completion_rate'] = (rider_stats['completed_trips'] / rider_stats['total_trips'] * 100)

        return rider_stats.sort_values('total_trips', ascending=False).head(top_n)

    def segment_users_by_activity(self, n_clusters=4):
        """
        Segment users into clusters based on activity patterns

        Args:
            n_clusters: Number of user segments to create

        Returns:
            DataFrame with user segments
        """
        # Aggregate rider metrics
        rider_metrics = self.trips.groupby('rider_id').agg({
            '_id': 'count',
            'amount': ['sum', 'mean'],
            'total_distance': 'sum',
            'ride_status': lambda x: (x == 'completed').sum()
        })

        rider_metrics.columns = ['trip_count', 'total_spent', 'avg_fare', 'total_distance', 'completed_trips']
        rider_metrics['completion_rate'] = rider_metrics['completed_trips'] / rider_metrics['trip_count']

        # Remove NaN values
        rider_metrics = rider_metrics.dropna()

        if len(rider_metrics) < n_clusters:
            return rider_metrics

        # Standardize features
        scaler = StandardScaler()
        features = ['trip_count', 'total_spent', 'avg_fare', 'completion_rate']
        X = scaler.fit_transform(rider_metrics[features])

        # K-means clustering
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        rider_metrics['segment'] = kmeans.fit_predict(X)

        # Label segments based on characteristics
        segment_labels = []
        for i in range(n_clusters):
            cluster_data = rider_metrics[rider_metrics['segment'] == i]
            avg_trips = cluster_data['trip_count'].mean()
            avg_spend = cluster_data['total_spent'].mean()

            if avg_trips > rider_metrics['trip_count'].quantile(0.75):
                label = 'High Frequency'
            elif avg_spend > rider_metrics['total_spent'].quantile(0.75):
                label = 'High Value'
            elif avg_trips < rider_metrics['trip_count'].quantile(0.25):
                label = 'Low Frequency'
            else:
                label = 'Regular User'

            segment_labels.append((i, label))

        # Map segment numbers to labels
        label_map = dict(segment_labels)
        rider_metrics['segment_label'] = rider_metrics['segment'].map(label_map)

        return rider_metrics

    def get_retention_metrics(self):
        """Calculate user retention metrics"""
        if 'accept_at' not in self.trips.columns:
            return {}

        # Get first and last trip for each rider
        rider_activity = self.trips.groupby('rider_id')['accept_at'].agg(['min', 'max', 'count'])
        rider_activity.columns = ['first_trip', 'last_trip', 'total_trips']

        # Calculate days since first trip
        latest_date = self.trips['accept_at'].max()
        rider_activity['days_active'] = (rider_activity['last_trip'] - rider_activity['first_trip']).dt.days
        rider_activity['days_since_last_trip'] = (latest_date - rider_activity['last_trip']).dt.days

        # Define churn (no trip in last 30 days)
        churned = len(rider_activity[rider_activity['days_since_last_trip'] > 30])
        active = len(rider_activity[rider_activity['days_since_last_trip'] <= 30])

        return {
            'total_riders': len(rider_activity),
            'active_riders': active,
            'churned_riders': churned,
            'churn_rate': (churned / len(rider_activity) * 100) if len(rider_activity) > 0 else 0,
            'avg_lifetime_days': rider_activity['days_active'].mean(),
            'avg_trips_per_rider': rider_activity['total_trips'].mean()
        }

    # =============================================
    # GEOGRAPHIC INSIGHTS
    # =============================================

    def get_area_analysis(self):
        """Analyze trip patterns by area"""
        area_stats = self.trips.groupby('request_area_name').agg({
            '_id': 'count',
            'ride_status': lambda x: (x == 'completed').sum(),
            'amount': 'sum',
            'total_distance': 'mean'
        }).rename(columns={
            '_id': 'total_requests',
            'ride_status': 'completed_trips',
            'amount': 'total_revenue',
            'total_distance': 'avg_distance'
        }).sort_values('total_requests', ascending=False)

        area_stats['completion_rate'] = (area_stats['completed_trips'] / area_stats['total_requests'] * 100)

        return area_stats

    def get_lga_analysis(self):
        """Analyze trip patterns by LGA (Local Government Area)"""
        lga_stats = self.trips.groupby('request_lga').agg({
            '_id': 'count',
            'ride_status': lambda x: (x == 'completed').sum(),
            'amount': 'sum'
        }).rename(columns={
            '_id': 'total_requests',
            'ride_status': 'completed_trips',
            'amount': 'total_revenue'
        }).sort_values('total_requests', ascending=False)

        return lga_stats

    def get_hotspot_locations(self, top_n=20):
        """Identify geographic hotspots for ride requests"""
        # Group by coordinates
        hotspots = self.trips.groupby(['start_lat', 'start_lon']).agg({
            '_id': 'count',
            'start_address': lambda x: x.mode()[0] if len(x) > 0 else 'Unknown'
        }).rename(columns={'_id': 'request_count', 'start_address': 'location'})

        hotspots = hotspots.sort_values('request_count', ascending=False).head(top_n)

        return hotspots.reset_index()

    def get_route_efficiency(self):
        """Analyze route efficiency metrics"""
        completed = self.trips[self.trips['ride_status'] == 'completed'].copy()

        if 'est_dst' in completed.columns and 'total_distance' in completed.columns:
            completed['est_dst'] = pd.to_numeric(completed['est_dst'], errors='coerce')
            completed['distance_variance'] = completed['total_distance'] - completed['est_dst']
            completed['efficiency_ratio'] = completed['est_dst'] / completed['total_distance']

            return {
                'avg_estimated_distance': completed['est_dst'].mean(),
                'avg_actual_distance': completed['total_distance'].mean(),
                'avg_variance': completed['distance_variance'].mean(),
                'median_efficiency_ratio': completed['efficiency_ratio'].median(),
                'overestimated_pct': (completed['distance_variance'] < 0).sum() / len(completed) * 100
            }

        return {}


    # =============================================
    # TRANSIT PATTERN ANALYTICS
    # =============================================

    def _map_destinations_to_areas(self):
        """Map destination coordinates to area names using nearest neighbor"""
        # Use cached version if available
        if hasattr(self, '_cached_trips_with_areas') and self._cached_trips_with_areas is not None:
            return self._cached_trips_with_areas

        from sklearn.neighbors import NearestNeighbors

        completed = self.trips[self.trips['ride_status'] == 'completed'].copy()

        # Build reference from pickup areas
        area_coords = completed.groupby('request_area_name').agg({
            'start_lat': 'mean',
            'start_lon': 'mean'
        }).dropna()

        if len(area_coords) == 0:
            return completed

        # Nearest neighbor to assign destinations to areas
        nn = NearestNeighbors(n_neighbors=1, algorithm='ball_tree')
        nn.fit(area_coords[['start_lat', 'start_lon']].values)

        valid_mask = completed['end_lat'].notna() & completed['end_lon'].notna()
        valid_trips = completed[valid_mask].copy()

        if len(valid_trips) == 0:
            return completed

        distances, indices = nn.kneighbors(valid_trips[['end_lat', 'end_lon']].values)
        valid_trips['end_area'] = area_coords.index[indices.flatten()].values
        valid_trips['start_area'] = valid_trips['request_area_name']
        valid_trips['corridor'] = valid_trips['start_area'].astype(str) + ' → ' + valid_trips['end_area'].astype(str)

        # Cache the result
        self._cached_trips_with_areas = valid_trips
        return valid_trips

    def get_transit_corridors(self, top_n=30):
        """
        Get top transit corridors with user counts

        Returns:
            DataFrame with corridor stats
        """
        trips_with_areas = self._map_destinations_to_areas()

        # Filter out NA corridors
        trips_with_areas = trips_with_areas[
            trips_with_areas['start_area'].notna() &
            trips_with_areas['end_area'].notna()
        ]

        corridors = trips_with_areas.groupby('corridor').agg(
            unique_users=('rider_id', 'nunique'),
            total_trips=('_id', 'count')
        ).sort_values('unique_users', ascending=False)

        return corridors.head(top_n)

    def identify_corridor_commuters(self, min_trips=3, consistency_threshold=0.3):
        """
        Identify users with consistent corridor patterns (area-based, not exact address)

        Args:
            min_trips: Minimum trips on same corridor
            consistency_threshold: Minimum % of trips on primary corridor

        Returns:
            DataFrame of users with corridor patterns
        """
        trips_with_areas = self._map_destinations_to_areas()

        # Filter valid corridors
        trips_with_areas = trips_with_areas[
            trips_with_areas['start_area'].notna() &
            trips_with_areas['end_area'].notna()
        ]

        # User corridor stats
        user_corridors = trips_with_areas.groupby(['rider_id', 'corridor']).agg({
            '_id': 'count',
            'hour': lambda x: int(x.mode().iloc[0]) if len(x) > 0 else 12
        }).rename(columns={'_id': 'corridor_trips', 'hour': 'typical_hour'})
        user_corridors = user_corridors.reset_index()

        # Get total trips per user
        user_totals = trips_with_areas.groupby('rider_id').agg({
            '_id': 'count',
            'amount': 'sum'
        }).rename(columns={'_id': 'total_trips', 'amount': 'total_spent'})

        user_corridors = user_corridors.merge(user_totals, on='rider_id')
        user_corridors['consistency'] = user_corridors['corridor_trips'] / user_corridors['total_trips']

        # Filter to users meeting criteria
        pattern_users = user_corridors[
            (user_corridors['corridor_trips'] >= min_trips) &
            (user_corridors['consistency'] >= consistency_threshold)
        ].copy()

        # Classify by time
        def classify_commuter(hour):
            if 6 <= hour < 10:
                return 'Morning Commuter'
            elif 16 <= hour < 20:
                return 'Evening Commuter'
            else:
                return 'Flexible Traveler'

        pattern_users['commuter_type'] = pattern_users['typical_hour'].apply(classify_commuter)

        return pattern_users.sort_values('corridor_trips', ascending=False)

    def get_corridor_time_patterns(self, corridor_name=None):
        """
        Get time-of-day patterns for corridors

        Args:
            corridor_name: Specific corridor to analyze, or None for all

        Returns:
            DataFrame with time patterns
        """
        trips_with_areas = self._map_destinations_to_areas()

        trips_with_areas['time_slot'] = pd.cut(
            trips_with_areas['hour'],
            bins=[0, 6, 10, 16, 20, 24],
            labels=['Night (12-6am)', 'Morning (6-10am)', 'Midday (10am-4pm)', 'Evening (4-8pm)', 'Late Night (8pm-12am)']
        )

        if corridor_name:
            trips_with_areas = trips_with_areas[trips_with_areas['corridor'] == corridor_name]

        time_patterns = trips_with_areas.groupby(['corridor', 'time_slot']).agg(
            users=('rider_id', 'nunique'),
            trips=('_id', 'count')
        ).reset_index()

        return time_patterns

    def get_bidirectional_corridor_users(self, min_trips=2):
        """
        Get users who travel on corridors in BOTH directions (to and fro)
        during morning AND evening hours.

        Args:
            min_trips: Minimum trips to qualify

        Returns:
            Dictionary with corridor -> user dataframe mapping
        """
        trips_with_areas = self._map_destinations_to_areas()

        # Filter valid trips
        trips_with_areas = trips_with_areas[
            trips_with_areas['start_area'].notna() &
            trips_with_areas['end_area'].notna()
        ].copy()

        # Define time periods
        trips_with_areas['is_morning'] = (trips_with_areas['hour'] >= 6) & (trips_with_areas['hour'] < 10)
        trips_with_areas['is_evening'] = (trips_with_areas['hour'] >= 16) & (trips_with_areas['hour'] < 20)

        # Create normalized corridor (alphabetically sorted to group A→B and B→A together)
        def normalize_corridor(row):
            areas = sorted([str(row['start_area']), str(row['end_area'])])
            return f"{areas[0]} ↔ {areas[1]}"

        trips_with_areas['normalized_corridor'] = trips_with_areas.apply(normalize_corridor, axis=1)

        # Find users who travel on each corridor
        corridor_users = {}

        for corridor in trips_with_areas['normalized_corridor'].unique():
            corridor_trips = trips_with_areas[trips_with_areas['normalized_corridor'] == corridor]

            # Group by user
            user_stats = corridor_trips.groupby('rider_id').agg({
                '_id': 'count',
                'is_morning': 'sum',
                'is_evening': 'sum',
                'amount': 'sum'
            }).rename(columns={
                '_id': 'total_trips',
                'is_morning': 'morning_trips',
                'is_evening': 'evening_trips',
                'amount': 'total_spent'
            })

            # Filter users with both morning AND evening trips
            qualified_users = user_stats[
                (user_stats['total_trips'] >= min_trips) &
                (user_stats['morning_trips'] >= 1) &
                (user_stats['evening_trips'] >= 1)
            ]

            if len(qualified_users) > 0:
                corridor_users[corridor] = qualified_users.reset_index()

        return corridor_users

    def get_corridor_users_with_contacts(self, corridor_name, min_trips=2):
        """
        Get users for a specific corridor with their contact details

        Args:
            corridor_name: The corridor to get users for
            min_trips: Minimum trips to qualify

        Returns:
            DataFrame with user details (name, phone, email)
        """
        trips_with_areas = self._map_destinations_to_areas()

        # Filter valid trips
        trips_with_areas = trips_with_areas[
            trips_with_areas['start_area'].notna() &
            trips_with_areas['end_area'].notna()
        ].copy()

        # Define time periods
        trips_with_areas['is_morning'] = (trips_with_areas['hour'] >= 6) & (trips_with_areas['hour'] < 10)
        trips_with_areas['is_evening'] = (trips_with_areas['hour'] >= 16) & (trips_with_areas['hour'] < 20)

        # Create normalized corridor
        def normalize_corridor(row):
            areas = sorted([str(row['start_area']), str(row['end_area'])])
            return f"{areas[0]} ↔ {areas[1]}"

        trips_with_areas['normalized_corridor'] = trips_with_areas.apply(normalize_corridor, axis=1)

        # Filter to this corridor
        corridor_trips = trips_with_areas[trips_with_areas['normalized_corridor'] == corridor_name]

        if len(corridor_trips) == 0:
            return pd.DataFrame()

        # Group by user
        user_stats = corridor_trips.groupby('rider_id').agg({
            '_id': 'count',
            'is_morning': 'sum',
            'is_evening': 'sum',
            'amount': 'sum',
            'rider_name': 'first',
            'rider_phone': 'first'
        }).rename(columns={
            '_id': 'total_trips',
            'is_morning': 'morning_trips',
            'is_evening': 'evening_trips',
            'amount': 'total_spent',
            'rider_name': 'name',
            'rider_phone': 'phone'
        })

        # Filter users with both morning AND evening trips
        qualified_users = user_stats[
            (user_stats['total_trips'] >= min_trips) &
            (user_stats['morning_trips'] >= 1) &
            (user_stats['evening_trips'] >= 1)
        ].copy()

        if len(qualified_users) == 0:
            return pd.DataFrame()

        # Join with users table to get email
        if self.users is not None and 'email' in self.users.columns:
            # Match on rider_id
            qualified_users = qualified_users.reset_index()
            user_emails = self.users[['_id', 'email']].rename(columns={'_id': 'rider_id'})
            qualified_users = qualified_users.merge(user_emails, on='rider_id', how='left')
        else:
            qualified_users = qualified_users.reset_index()
            qualified_users['email'] = None

        # Select and order columns (hide rider_id)
        result_cols = ['name', 'phone', 'email', 'total_trips', 'morning_trips', 'evening_trips', 'total_spent']
        result_cols = [c for c in result_cols if c in qualified_users.columns]

        return qualified_users[result_cols].sort_values('total_trips', ascending=False)

    def get_all_commuter_corridors(self, min_users=5, min_trips=2):
        """
        Get all corridors that have users with morning+evening bidirectional patterns

        Args:
            min_users: Minimum users per corridor to include
            min_trips: Minimum trips per user

        Returns:
            DataFrame with corridor stats
        """
        corridor_users = self.get_bidirectional_corridor_users(min_trips=min_trips)

        corridor_stats = []
        for corridor, users_df in corridor_users.items():
            if len(users_df) >= min_users:
                corridor_stats.append({
                    'corridor': corridor,
                    'total_users': len(users_df),
                    'total_trips': users_df['total_trips'].sum(),
                    'avg_trips_per_user': users_df['total_trips'].mean(),
                    'total_spent': users_df['total_spent'].sum()
                })

        if not corridor_stats:
            return pd.DataFrame()

        return pd.DataFrame(corridor_stats).sort_values('total_users', ascending=False)

    def get_user_route_patterns(self, min_trips=3):
        """
        Extract frequent routes for each user (pickup → dropoff patterns)

        Args:
            min_trips: Minimum trips on a route to consider it a pattern

        Returns:
            DataFrame with user route patterns
        """
        # Get completed trips with location data
        completed = self.trips[self.trips['ride_status'] == 'completed'].copy()

        # Create route identifier
        completed['route'] = completed['start_address'].fillna('Unknown') + ' → ' + completed['end_address'].fillna('Unknown')

        # Count routes per user
        user_routes = completed.groupby(['rider_id', 'route']).agg({
            '_id': 'count',
            'hour': lambda x: list(x),
            'day_of_week': lambda x: list(x),
            'start_lat': 'first',
            'start_lon': 'first',
            'end_lat': 'first',
            'end_lon': 'first',
            'start_address': 'first',
            'end_address': 'first'
        }).rename(columns={'_id': 'trip_count'})

        # Filter to frequent routes
        user_routes = user_routes[user_routes['trip_count'] >= min_trips].reset_index()

        # Calculate most common hour for each route
        user_routes['primary_hour'] = user_routes['hour'].apply(
            lambda x: max(set(x), key=x.count) if x else None
        )

        # Determine time period
        def get_time_period(hour):
            if hour is None:
                return 'Unknown'
            if 6 <= hour < 10:
                return 'Morning Commute'
            elif 10 <= hour < 16:
                return 'Midday'
            elif 16 <= hour < 20:
                return 'Evening Commute'
            else:
                return 'Night'

        user_routes['time_period'] = user_routes['primary_hour'].apply(get_time_period)

        return user_routes

    def get_user_time_patterns(self):
        """
        Extract time-of-day usage patterns for each user

        Returns:
            DataFrame with user time patterns
        """
        if 'hour' not in self.trips.columns:
            return pd.DataFrame()

        completed = self.trips[self.trips['ride_status'] == 'completed'].copy()

        # Create hour distribution per user
        user_hours = completed.groupby(['rider_id', 'hour']).size().unstack(fill_value=0)

        # Calculate peak hours for each user
        user_time_patterns = pd.DataFrame(index=user_hours.index)
        user_time_patterns['total_trips'] = user_hours.sum(axis=1)
        user_time_patterns['peak_hour'] = user_hours.idxmax(axis=1)

        # Calculate time period distribution
        morning = user_hours[[h for h in range(6, 10) if h in user_hours.columns]].sum(axis=1)
        midday = user_hours[[h for h in range(10, 16) if h in user_hours.columns]].sum(axis=1)
        evening = user_hours[[h for h in range(16, 20) if h in user_hours.columns]].sum(axis=1)
        night = user_hours[[h for h in list(range(0, 6)) + list(range(20, 24)) if h in user_hours.columns]].sum(axis=1)

        total = morning + midday + evening + night
        total = total.replace(0, 1)  # Avoid division by zero

        user_time_patterns['morning_pct'] = (morning / total * 100).round(1)
        user_time_patterns['midday_pct'] = (midday / total * 100).round(1)
        user_time_patterns['evening_pct'] = (evening / total * 100).round(1)
        user_time_patterns['night_pct'] = (night / total * 100).round(1)

        # Determine primary time pattern
        def get_primary_pattern(row):
            patterns = {
                'Morning Commuter': row['morning_pct'],
                'Midday User': row['midday_pct'],
                'Evening Commuter': row['evening_pct'],
                'Night User': row['night_pct']
            }
            return max(patterns, key=patterns.get)

        user_time_patterns['primary_pattern'] = user_time_patterns.apply(get_primary_pattern, axis=1)

        return user_time_patterns

    def identify_commuters(self, min_trips=5, consistency_threshold=0.6):
        """
        Identify users with consistent commute patterns (same route, same time)

        Args:
            min_trips: Minimum trips to qualify as commuter
            consistency_threshold: Minimum % of trips on primary route

        Returns:
            DataFrame of identified commuters with their patterns
        """
        completed = self.trips[self.trips['ride_status'] == 'completed'].copy()

        # Create route identifier
        completed['route'] = completed['start_address'].fillna('Unknown') + ' → ' + completed['end_address'].fillna('Unknown')

        # Get user trip counts and primary route
        user_stats = completed.groupby('rider_id').agg({
            '_id': 'count',
            'route': lambda x: x.mode()[0] if len(x) > 0 else None,
            'amount': 'sum'
        }).rename(columns={'_id': 'total_trips', 'route': 'primary_route', 'amount': 'total_spent'})

        # Count trips on primary route
        def count_primary_route_trips(rider_id, primary_route):
            rider_trips = completed[completed['rider_id'] == rider_id]
            return (rider_trips['route'] == primary_route).sum()

        # Get route consistency for users with enough trips
        qualified_users = user_stats[user_stats['total_trips'] >= min_trips].copy()

        if len(qualified_users) == 0:
            return pd.DataFrame()

        # Calculate consistency (% of trips on primary route)
        primary_route_counts = completed.groupby(['rider_id', 'route']).size().reset_index(name='route_trips')
        primary_route_counts = primary_route_counts.loc[
            primary_route_counts.groupby('rider_id')['route_trips'].idxmax()
        ].set_index('rider_id')

        qualified_users = qualified_users.join(primary_route_counts['route_trips'])
        qualified_users['route_consistency'] = (qualified_users['route_trips'] / qualified_users['total_trips']).round(3)

        # Filter to consistent commuters
        commuters = qualified_users[qualified_users['route_consistency'] >= consistency_threshold].copy()

        # Add time patterns for commuters
        if len(commuters) > 0:
            commuter_trips = completed[completed['rider_id'].isin(commuters.index)]
            commuter_hours = commuter_trips.groupby('rider_id')['hour'].agg(
                lambda x: x.mode()[0] if len(x) > 0 else None
            )
            commuters['typical_hour'] = commuter_hours

            # Add day pattern
            commuter_days = commuter_trips.groupby('rider_id')['day_of_week'].agg(
                lambda x: list(x.mode()) if len(x) > 0 else []
            )
            commuters['typical_days'] = commuter_days

            # Classify commuter type
            def classify_commuter(row):
                hour = row['typical_hour']
                if hour is None:
                    return 'Unknown'
                if 6 <= hour < 10:
                    return 'Morning Commuter'
                elif 16 <= hour < 20:
                    return 'Evening Commuter'
                else:
                    return 'Flexible Commuter'

            commuters['commuter_type'] = commuters.apply(classify_commuter, axis=1)

        return commuters.sort_values('total_trips', ascending=False)

    def cluster_users_by_transit_patterns(self, n_clusters=5, min_trips=3):
        """
        Cluster users based on similar transit patterns (routes + timing)

        Args:
            n_clusters: Number of clusters to create
            min_trips: Minimum trips to include user

        Returns:
            DataFrame with user clusters and pattern descriptions
        """
        completed = self.trips[self.trips['ride_status'] == 'completed'].copy()

        # Build feature matrix for each user
        user_features = completed.groupby('rider_id').agg({
            '_id': 'count',
            'amount': ['sum', 'mean'],
            'total_distance': 'mean',
            'hour': lambda x: x.mode()[0] if len(x) > 0 else 12,
            'start_lat': 'mean',
            'start_lon': 'mean',
            'end_lat': 'mean',
            'end_lon': 'mean'
        })

        user_features.columns = [
            'trip_count', 'total_spent', 'avg_fare', 'avg_distance',
            'typical_hour', 'avg_start_lat', 'avg_start_lon', 'avg_end_lat', 'avg_end_lon'
        ]

        # Filter users with minimum trips
        user_features = user_features[user_features['trip_count'] >= min_trips].copy()

        # Add time pattern features
        time_patterns = self.get_user_time_patterns()
        if not time_patterns.empty:
            user_features = user_features.join(
                time_patterns[['morning_pct', 'midday_pct', 'evening_pct', 'night_pct']],
                how='left'
            ).fillna(25)  # Default to equal distribution

        # Add route consistency
        completed['route'] = completed['start_address'].fillna('') + '→' + completed['end_address'].fillna('')
        route_counts = completed.groupby('rider_id')['route'].agg(
            lambda x: x.value_counts().iloc[0] / len(x) if len(x) > 0 else 0
        )
        user_features['route_consistency'] = route_counts
        user_features['route_consistency'] = user_features['route_consistency'].fillna(0)

        # Remove NaN values
        user_features = user_features.dropna()

        if len(user_features) < n_clusters:
            return user_features

        # Prepare features for clustering
        cluster_features = [
            'trip_count', 'avg_fare', 'avg_distance', 'typical_hour',
            'avg_start_lat', 'avg_start_lon', 'avg_end_lat', 'avg_end_lon',
            'morning_pct', 'evening_pct', 'route_consistency'
        ]

        # Filter to available features
        available_features = [f for f in cluster_features if f in user_features.columns]

        # Standardize features
        scaler = StandardScaler()
        X = scaler.fit_transform(user_features[available_features])

        # K-means clustering
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        user_features['cluster'] = kmeans.fit_predict(X)

        # Analyze and label clusters
        cluster_profiles = []
        for i in range(n_clusters):
            cluster_data = user_features[user_features['cluster'] == i]

            profile = {
                'cluster': i,
                'user_count': len(cluster_data),
                'avg_trips': cluster_data['trip_count'].mean(),
                'avg_spent': cluster_data['total_spent'].mean(),
                'avg_distance': cluster_data['avg_distance'].mean(),
                'typical_hour': cluster_data['typical_hour'].mean(),
                'route_consistency': cluster_data['route_consistency'].mean(),
                'morning_pct': cluster_data['morning_pct'].mean() if 'morning_pct' in cluster_data.columns else 0,
                'evening_pct': cluster_data['evening_pct'].mean() if 'evening_pct' in cluster_data.columns else 0
            }

            # Generate label based on characteristics
            label_parts = []

            # Frequency label
            if profile['avg_trips'] > user_features['trip_count'].quantile(0.75):
                label_parts.append('High-Frequency')
            elif profile['avg_trips'] < user_features['trip_count'].quantile(0.25):
                label_parts.append('Occasional')

            # Time pattern label
            if profile['morning_pct'] > 40:
                label_parts.append('Morning')
            elif profile['evening_pct'] > 40:
                label_parts.append('Evening')

            # Route consistency label
            if profile['route_consistency'] > 0.5:
                label_parts.append('Commuter')
            elif profile['route_consistency'] < 0.2:
                label_parts.append('Explorer')

            # Distance label
            if profile['avg_distance'] > user_features['avg_distance'].quantile(0.75):
                label_parts.append('Long-Distance')
            elif profile['avg_distance'] < user_features['avg_distance'].quantile(0.25):
                label_parts.append('Short-Trip')

            profile['label'] = ' '.join(label_parts) if label_parts else f'Segment {i+1}'
            cluster_profiles.append(profile)

        # Map labels to users
        label_map = {p['cluster']: p['label'] for p in cluster_profiles}
        user_features['transit_segment'] = user_features['cluster'].map(label_map)

        return user_features, pd.DataFrame(cluster_profiles)

    def find_similar_users(self, user_id, top_n=10):
        """
        Find users with similar transit patterns to a given user

        Args:
            user_id: The rider_id to find similar users for
            top_n: Number of similar users to return

        Returns:
            DataFrame of similar users with similarity scores
        """
        completed = self.trips[self.trips['ride_status'] == 'completed'].copy()

        # Check if user exists
        if user_id not in completed['rider_id'].values:
            return pd.DataFrame()

        # Build user feature vectors
        completed['route'] = completed['start_address'].fillna('') + '→' + completed['end_address'].fillna('')

        user_profiles = completed.groupby('rider_id').agg({
            '_id': 'count',
            'start_lat': 'mean',
            'start_lon': 'mean',
            'end_lat': 'mean',
            'end_lon': 'mean',
            'hour': lambda x: x.mode()[0] if len(x) > 0 else 12,
            'amount': 'mean',
            'total_distance': 'mean'
        }).rename(columns={'_id': 'trip_count'})

        # Get target user profile
        if user_id not in user_profiles.index:
            return pd.DataFrame()

        target = user_profiles.loc[user_id]

        # Calculate similarity (Euclidean distance in normalized space)
        features = ['start_lat', 'start_lon', 'end_lat', 'end_lon', 'hour', 'total_distance']

        scaler = StandardScaler()
        X = scaler.fit_transform(user_profiles[features].fillna(0))

        target_idx = user_profiles.index.get_loc(user_id)
        target_vector = X[target_idx]

        # Calculate distances
        distances = np.sqrt(((X - target_vector) ** 2).sum(axis=1))
        user_profiles['distance'] = distances
        user_profiles['similarity_score'] = 1 / (1 + distances)  # Convert to similarity

        # Get top similar users (excluding self)
        similar = user_profiles[user_profiles.index != user_id].nlargest(top_n, 'similarity_score')

        # Add user names if available
        if 'rider_name' in completed.columns:
            names = completed.groupby('rider_id')['rider_name'].first()
            similar = similar.join(names)

        return similar[['trip_count', 'hour', 'total_distance', 'similarity_score'] +
                      (['rider_name'] if 'rider_name' in similar.columns else [])]

    def get_transit_pattern_summary(self):
        """
        Get a comprehensive summary of transit patterns in the data

        Returns:
            Dictionary with pattern summaries
        """
        # Use corridor-based commuter identification (area-based, not exact address)
        corridor_commuters = self.identify_corridor_commuters(min_trips=3, consistency_threshold=0.3)
        time_patterns = self.get_user_time_patterns()

        summary = {
            'total_users_analyzed': len(time_patterns) if not time_patterns.empty else 0,
            'identified_commuters': corridor_commuters['rider_id'].nunique() if not corridor_commuters.empty else 0,
        }

        if not time_patterns.empty:
            pattern_dist = time_patterns['primary_pattern'].value_counts()
            summary['time_pattern_distribution'] = pattern_dist.to_dict()

        if not corridor_commuters.empty:
            commuter_types = corridor_commuters['commuter_type'].value_counts()
            summary['commuter_type_distribution'] = commuter_types.to_dict()
            summary['avg_commuter_trips'] = corridor_commuters['total_trips'].mean()
            summary['avg_commuter_spend'] = corridor_commuters['total_spent'].mean()

        return summary


if __name__ == "__main__":
    # Example usage
    print("Analytics module loaded successfully")
    print("Import this module in your dashboard: from analytics import RideAnalytics")
