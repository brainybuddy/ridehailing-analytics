"""
Lagos Ride-Hailing Analytics Dashboard
Interactive dashboard for comprehensive ride-hailing data analysis
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import folium
from streamlit_folium import folium_static
from data_loader_db import RideDataLoader
from analytics import RideAnalytics
import warnings
import io
warnings.filterwarnings('ignore')


# Page configuration
st.set_page_config(
    page_title="Lagos Ride Analytics",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
    <style>
    .big-metric {font-size: 24px; font-weight: bold; color: #1f77b4;}
    .metric-label {font-size: 14px; color: #666;}
    </style>
""", unsafe_allow_html=True)


@st.cache_data
def load_data(sample_frac=None):
    """Load and cache data from database"""
    loader = RideDataLoader()
    trips, users = loader.load_all(sample_frac=sample_frac)
    return trips, users


@st.cache_resource
def initialize_analytics(_trips, _users):
    """Initialize analytics engine"""
    return RideAnalytics(_trips, _users)


@st.cache_data(show_spinner=False)
def get_cached_commuter_corridors(_analytics_id, min_users=3, min_trips=2):
    """Cache corridor analysis results"""
    analytics = st.session_state.get('analytics')
    if analytics is None:
        return None
    return analytics.get_all_commuter_corridors(min_users=min_users, min_trips=min_trips)


@st.cache_data(show_spinner=False)
def get_cached_corridor_users(_analytics_id, corridor_name, min_trips=2):
    """Cache corridor user details"""
    analytics = st.session_state.get('analytics')
    if analytics is None:
        return None
    return analytics.get_corridor_users_with_contacts(corridor_name, min_trips=min_trips)


@st.cache_data(show_spinner=False)
def get_cached_transit_summary(_analytics_id):
    """Cache transit pattern summary"""
    analytics = st.session_state.get('analytics')
    if analytics is None:
        return None
    return analytics.get_transit_pattern_summary()


@st.cache_data(show_spinner=False)
def get_cached_transit_corridors(_analytics_id, top_n=20):
    """Cache transit corridors"""
    analytics = st.session_state.get('analytics')
    if analytics is None:
        return None
    return analytics.get_transit_corridors(top_n=top_n)


# ============ OVERVIEW PAGE CACHING ============
@st.cache_data(show_spinner=False)
def get_cached_trip_overview(_analytics_id):
    analytics = st.session_state.get('analytics')
    if analytics is None:
        return None
    return analytics.get_trip_overview()


@st.cache_data(show_spinner=False)
def get_cached_revenue_overview(_analytics_id):
    analytics = st.session_state.get('analytics')
    if analytics is None:
        return None
    return analytics.get_revenue_overview()


@st.cache_data(show_spinner=False)
def get_cached_trip_trends(_analytics_id, freq='D'):
    analytics = st.session_state.get('analytics')
    if analytics is None:
        return None
    return analytics.get_trip_trends(freq=freq)


@st.cache_data(show_spinner=False)
def get_cached_revenue_trends(_analytics_id, freq='D'):
    analytics = st.session_state.get('analytics')
    if analytics is None:
        return None
    return analytics.get_revenue_trends(freq=freq)


# ============ TRIP ANALYTICS CACHING ============
@st.cache_data(show_spinner=False)
def get_cached_peak_hours(_analytics_id):
    analytics = st.session_state.get('analytics')
    if analytics is None:
        return None
    return analytics.get_peak_hours()


@st.cache_data(show_spinner=False)
def get_cached_popular_routes(_analytics_id, top_n=20):
    analytics = st.session_state.get('analytics')
    if analytics is None:
        return None
    return analytics.get_popular_routes(top_n=top_n)


@st.cache_data(show_spinner=False)
def get_cached_cancellation_analysis(_analytics_id):
    analytics = st.session_state.get('analytics')
    if analytics is None:
        return None
    return analytics.get_cancellation_analysis()


# ============ FINANCIAL METRICS CACHING ============
@st.cache_data(show_spinner=False)
def get_cached_payment_analysis(_analytics_id):
    analytics = st.session_state.get('analytics')
    if analytics is None:
        return None
    return analytics.get_payment_analysis()


@st.cache_data(show_spinner=False)
def get_cached_fare_distribution(_analytics_id):
    analytics = st.session_state.get('analytics')
    if analytics is None:
        return None
    return analytics.get_fare_distribution()


# ============ USER BEHAVIOR CACHING ============
@st.cache_data(show_spinner=False)
def get_cached_retention_metrics(_analytics_id):
    analytics = st.session_state.get('analytics')
    if analytics is None:
        return None
    return analytics.get_retention_metrics()


@st.cache_data(show_spinner=False)
def get_cached_driver_performance(_analytics_id, top_n=20):
    analytics = st.session_state.get('analytics')
    if analytics is None:
        return None
    return analytics.get_driver_performance(top_n=top_n)


@st.cache_data(show_spinner=False)
def get_cached_rider_behavior(_analytics_id, top_n=20):
    analytics = st.session_state.get('analytics')
    if analytics is None:
        return None
    return analytics.get_rider_behavior(top_n=top_n)


@st.cache_data(show_spinner=False)
def get_cached_user_segments(_analytics_id, n_clusters=4):
    analytics = st.session_state.get('analytics')
    if analytics is None:
        return None
    return analytics.segment_users_by_activity(n_clusters=n_clusters)


# ============ GEOGRAPHIC CACHING ============
@st.cache_data(show_spinner=False)
def get_cached_area_analysis(_analytics_id):
    analytics = st.session_state.get('analytics')
    if analytics is None:
        return None
    return analytics.get_area_analysis()


@st.cache_data(show_spinner=False)
def get_cached_lga_analysis(_analytics_id):
    analytics = st.session_state.get('analytics')
    if analytics is None:
        return None
    return analytics.get_lga_analysis()


@st.cache_data(show_spinner=False)
def get_cached_hotspot_locations(_analytics_id, top_n=100):
    analytics = st.session_state.get('analytics')
    if analytics is None:
        return None
    return analytics.get_hotspot_locations(top_n=top_n)


@st.cache_data(show_spinner=False)
def get_cached_route_efficiency(_analytics_id):
    analytics = st.session_state.get('analytics')
    if analytics is None:
        return None
    return analytics.get_route_efficiency()


def main():
    st.title("🚗 Lagos Ride-Hailing Analytics Dashboard")
    st.caption("⚡ First load computes analytics and caches results. Subsequent page visits will be much faster.")
    st.markdown("---")

    # Sidebar configuration
    st.sidebar.title("⚙️ Configuration")

    # Data loading options
    st.sidebar.header("Data Loading")
    load_option = st.sidebar.radio(
        "Dataset Size",
        ["Full Dataset (1.4GB)", "Sample 50%", "Sample 10%", "Sample 1%"],
        help="Choose dataset size. Start with sample for faster loading."
    )

    sample_map = {
        "Full Dataset (1.4GB)": None,
        "Sample 50%": 0.5,
        "Sample 10%": 0.1,
        "Sample 1%": 0.01
    }

    # Load data
    with st.spinner("Loading data..."):
        trips, users = load_data(sample_frac=sample_map[load_option])
        analytics = initialize_analytics(trips, users)
        # Store in session state for cached functions
        st.session_state['analytics'] = analytics
        st.session_state['analytics_id'] = id(analytics)

    st.sidebar.success(f"✅ Loaded {len(trips):,} trips and {len(users):,} users")

    # Navigation
    st.sidebar.markdown("---")
    st.sidebar.header("📊 Navigation")
    page = st.sidebar.selectbox(
        "Select Analysis",
        [
            "🏠 Overview & Commuters",
            "🔄 Transit Patterns",
            "🚕 Trip Analytics",
            "💰 Financial Metrics",
            "👥 User Behavior",
            "📍 Geographic Insights"
        ]
    )

    # Route to appropriate page
    if page == "🏠 Overview & Commuters":
        show_overview(analytics, trips, users)
    elif page == "🔄 Transit Patterns":
        show_transit_patterns(analytics, trips, users)
    elif page == "🚕 Trip Analytics":
        show_trip_analytics(analytics, trips)
    elif page == "💰 Financial Metrics":
        show_financial_metrics(analytics, trips)
    elif page == "👥 User Behavior":
        show_user_behavior(analytics, trips, users)
    elif page == "📍 Geographic Insights":
        show_geographic_insights(analytics, trips)


def show_overview(analytics, trips, users):
    """Display overview dashboard with Corridor Commuters as primary feature"""
    st.header("🎯 Lagos Ride-Hailing Intelligence")

    analytics_id = st.session_state.get('analytics_id', 0)

    # ============ PRIMARY FEATURE: CORRIDOR COMMUTERS ============
    st.subheader("🎯 Corridor Commuters - Target Customer Lists")
    st.markdown("""
    **Users who travel the same corridor in BOTH directions during morning AND evening hours.**
    These are verified daily commuters - your highest-value targets for EV services.
    """)

    with st.spinner("Loading commuter corridors..."):
        try:
            commuter_corridors = get_cached_commuter_corridors(analytics_id, min_users=3, min_trips=2)
            if commuter_corridors is None:
                commuter_corridors = analytics.get_all_commuter_corridors(min_users=3, min_trips=2)

            if commuter_corridors is not None and not commuter_corridors.empty:
                # Key metrics
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Total Corridors", f"{len(commuter_corridors):,}")
                with col2:
                    st.metric("Total Commuters", f"{commuter_corridors['total_users'].sum():,}")
                with col3:
                    st.metric("Total Trips", f"{commuter_corridors['total_trips'].sum():,}")
                with col4:
                    st.metric("Total Spend", f"₦{commuter_corridors['total_spent'].sum():,.0f}")

                # Corridor selector
                st.markdown("---")
                st.write("**Select a corridor to view & download commuter contact list:**")

                selected_corridor = st.selectbox(
                    "Choose Corridor",
                    options=commuter_corridors['corridor'].tolist(),
                    format_func=lambda x: f"{x} ({commuter_corridors[commuter_corridors['corridor']==x]['total_users'].values[0]} users)",
                    key="overview_corridor_select"
                )

                if selected_corridor:
                    with st.spinner(f"Loading users for {selected_corridor}..."):
                        corridor_users = get_cached_corridor_users(analytics_id, selected_corridor, min_trips=2)
                        if corridor_users is None:
                            corridor_users = analytics.get_corridor_users_with_contacts(selected_corridor, min_trips=2)

                    if corridor_users is not None and not corridor_users.empty:
                        col1, col2 = st.columns([3, 1])

                        with col1:
                            st.write(f"**{len(corridor_users)} verified commuters** (Name, Phone, Email)")
                            display_users = corridor_users.copy()
                            if 'total_spent' in display_users.columns:
                                display_users['total_spent'] = display_users['total_spent'].apply(lambda x: f"₦{x:,.0f}")
                            st.dataframe(display_users, hide_index=True, use_container_width=True)

                        with col2:
                            # Excel download
                            excel_buffer = io.BytesIO()
                            with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                                corridor_users.to_excel(writer, sheet_name='Commuters', index=False)
                            excel_buffer.seek(0)
                            safe_filename = selected_corridor.replace(' ', '_').replace('/', '-').replace('↔', 'to')[:50]

                            st.download_button(
                                label=f"📥 Download Excel",
                                data=excel_buffer,
                                file_name=f"commuters_{safe_filename}.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                key="overview_download"
                            )

                            # Download all button
                            if st.button("📥 Download ALL Corridors", key="overview_download_all"):
                                with st.spinner("Generating..."):
                                    all_buffer = io.BytesIO()
                                    with pd.ExcelWriter(all_buffer, engine='openpyxl') as writer:
                                        for corridor in commuter_corridors['corridor'].tolist():
                                            users_df = analytics.get_corridor_users_with_contacts(corridor, min_trips=2)
                                            if users_df is not None and not users_df.empty:
                                                sheet_name = corridor[:28].replace('/', '-').replace('↔', '-')
                                                users_df.to_excel(writer, sheet_name=sheet_name, index=False)
                                    all_buffer.seek(0)
                                    st.download_button(
                                        label="📥 Download Now",
                                        data=all_buffer,
                                        file_name="all_corridor_commuters.xlsx",
                                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                        key="overview_download_all_file"
                                    )
            else:
                st.info("Loading corridor data... Please wait.")

        except Exception as e:
            st.error(f"Error loading corridors: {str(e)}")

    st.markdown("---")
    st.markdown("---")

    # ============ SECONDARY: OVERVIEW METRICS ============
    st.subheader("📊 Dataset Overview")

    trip_overview = get_cached_trip_overview(analytics_id) or analytics.get_trip_overview()
    revenue_overview = get_cached_revenue_overview(analytics_id) or analytics.get_revenue_overview()

    # Top metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Trips", f"{trip_overview['total_trips']:,}")
        st.metric("Completion Rate", f"{trip_overview['completion_rate']:.1f}%")

    with col2:
        st.metric("Total Revenue", f"₦{revenue_overview['total_revenue']:,.0f}")
        st.metric("Avg Fare", f"₦{revenue_overview['avg_fare_per_trip']:,.0f}")

    with col3:
        st.metric("Unique Drivers", f"{trip_overview['unique_drivers']:,}")
        st.metric("Unique Riders", f"{trip_overview['unique_riders']:,}")

    with col4:
        st.metric("Avg Trips/Day", f"{trip_overview['avg_trips_per_day']:.0f}")
        st.metric("Revenue/km", f"₦{revenue_overview['revenue_per_km']:,.0f}")

    st.markdown("---")

    # Trends
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Trip Trends")
        trends = get_cached_trip_trends(analytics_id, freq='D')
        if trends is None:
            trends = analytics.get_trip_trends(freq='D')
        if not trends.empty:
            fig = go.Figure()
            for status in trends.columns:
                fig.add_trace(go.Scatter(
                    x=trends.index,
                    y=trends[status],
                    name=status.title(),
                    mode='lines'
                ))
            fig.update_layout(
                xaxis_title="Date",
                yaxis_title="Number of Trips",
                hovermode='x unified',
                height=400
            )
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Revenue Trends")
        revenue_trends = get_cached_revenue_trends(analytics_id, freq='D')
        if revenue_trends is None:
            revenue_trends = analytics.get_revenue_trends(freq='D')
        if not revenue_trends.empty:
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=revenue_trends.index,
                y=revenue_trends['amount'],
                name='Revenue',
                fill='tozeroy'
            ))
            fig.update_layout(
                xaxis_title="Date",
                yaxis_title="Revenue (₦)",
                height=400
            )
            st.plotly_chart(fig, use_container_width=True)

    # Status distribution
    st.subheader("Trip Status Distribution")
    status_counts = trips['ride_status'].value_counts()
    fig = px.pie(
        values=status_counts.values,
        names=status_counts.index,
        title="Distribution of Trip Statuses"
    )
    st.plotly_chart(fig, use_container_width=True)


def show_trip_analytics(analytics, trips):
    """Display trip analytics page"""
    st.header("🚕 Trip Analytics")

    analytics_id = st.session_state.get('analytics_id', 0)

    # Peak hours analysis
    st.subheader("Peak Hours Analysis")
    peak_hours = get_cached_peak_hours(analytics_id)
    if peak_hours is None:
        peak_hours = analytics.get_peak_hours()

    if not peak_hours.empty:
        fig = make_subplots(specs=[[{"secondary_y": True}]])

        fig.add_trace(
            go.Bar(x=peak_hours.index, y=peak_hours['total_requests'], name="Total Requests"),
            secondary_y=False
        )

        fig.add_trace(
            go.Scatter(x=peak_hours.index, y=peak_hours['completion_rate'],
                      name="Completion Rate (%)", mode='lines+markers'),
            secondary_y=True
        )

        fig.update_xaxes(title_text="Hour of Day")
        fig.update_yaxes(title_text="Number of Requests", secondary_y=False)
        fig.update_yaxes(title_text="Completion Rate (%)", secondary_y=True)

        st.plotly_chart(fig, use_container_width=True)

    # Day of week analysis
    st.subheader("Day of Week Analysis")
    col1, col2 = st.columns(2)

    with col1:
        if 'day_of_week' in trips.columns:
            day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            day_counts = trips['day_of_week'].value_counts().reindex(day_order, fill_value=0)

            fig = px.bar(
                x=day_counts.index,
                y=day_counts.values,
                labels={'x': 'Day of Week', 'y': 'Number of Trips'},
                title="Trips by Day of Week"
            )
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        if 'day_of_week' in trips.columns:
            completed = trips[trips['ride_status'] == 'completed']
            completion_by_day = completed['day_of_week'].value_counts().reindex(day_order, fill_value=0)
            total_by_day = day_counts
            completion_rate_by_day = (completion_by_day / total_by_day * 100).fillna(0)

            fig = px.bar(
                x=completion_rate_by_day.index,
                y=completion_rate_by_day.values,
                labels={'x': 'Day of Week', 'y': 'Completion Rate (%)'},
                title="Completion Rate by Day of Week"
            )
            st.plotly_chart(fig, use_container_width=True)

    # Popular routes
    st.subheader("Top 20 Popular Routes")
    popular_routes = get_cached_popular_routes(analytics_id, top_n=20)
    if popular_routes is None:
        popular_routes = analytics.get_popular_routes(top_n=20)

    if not popular_routes.empty:
        display_routes = popular_routes.reset_index()
        display_routes['route'] = display_routes['start_address'].str[:30] + ' → ' + display_routes['end_address'].str[:30]

        fig = px.bar(
            display_routes,
            x='trip_count',
            y='route',
            orientation='h',
            labels={'trip_count': 'Number of Trips', 'route': 'Route'},
            title="Most Popular Routes"
        )
        fig.update_layout(height=600)
        st.plotly_chart(fig, use_container_width=True)

    # Cancellation analysis
    st.subheader("Cancellation Analysis")
    cancel_data = get_cached_cancellation_analysis(analytics_id)
    if cancel_data is None:
        cancel_data = analytics.get_cancellation_analysis()

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Total Cancellations", f"{cancel_data.get('total_cancelled', 0):,}")

    with col2:
        total_trips = len(trips)
        cancel_rate = (cancel_data.get('total_cancelled', 0) / total_trips * 100) if total_trips > 0 else 0
        st.metric("Cancellation Rate", f"{cancel_rate:.2f}%")

    with col3:
        st.metric("Avg Waiting Time (Cancelled)", f"{cancel_data.get('avg_waiting_time', 0):.1f}s")

    # Cancellation by hour
    if cancel_data.get('by_hour'):
        by_hour_df = pd.DataFrame(list(cancel_data['by_hour'].items()), columns=['Hour', 'Cancellations'])
        fig = px.line(
            by_hour_df,
            x='Hour',
            y='Cancellations',
            markers=True,
            title="Cancellations by Hour"
        )
        st.plotly_chart(fig, use_container_width=True)


def show_financial_metrics(analytics, trips):
    """Display financial metrics page"""
    st.header("💰 Financial Metrics")

    analytics_id = st.session_state.get('analytics_id', 0)
    revenue_overview = get_cached_revenue_overview(analytics_id) or analytics.get_revenue_overview()

    # Revenue metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Revenue", f"₦{revenue_overview['total_revenue']:,.0f}")

    with col2:
        st.metric("Total Fares", f"₦{revenue_overview['total_fares']:,.0f}")

    with col3:
        st.metric("Avg Fare/Trip", f"₦{revenue_overview['avg_fare_per_trip']:,.0f}")

    with col4:
        st.metric("Median Fare", f"₦{revenue_overview['median_fare']:,.0f}")

    st.markdown("---")

    # Revenue trends
    st.subheader("Revenue Trends")

    freq = st.selectbox("Time Granularity", ["Daily", "Weekly", "Monthly"])
    freq_map = {"Daily": "D", "Weekly": "W", "Monthly": "M"}

    revenue_trends = get_cached_revenue_trends(analytics_id, freq=freq_map[freq])
    if revenue_trends is None:
        revenue_trends = analytics.get_revenue_trends(freq=freq_map[freq])

    if not revenue_trends.empty:
        fig = make_subplots(specs=[[{"secondary_y": True}]])

        fig.add_trace(
            go.Bar(x=revenue_trends.index, y=revenue_trends['amount'], name="Revenue"),
            secondary_y=False
        )

        fig.add_trace(
            go.Scatter(x=revenue_trends.index, y=revenue_trends['avg_fare'],
                      name="Avg Fare", mode='lines+markers'),
            secondary_y=True
        )

        fig.update_xaxes(title_text="Date")
        fig.update_yaxes(title_text="Revenue (₦)", secondary_y=False)
        fig.update_yaxes(title_text="Average Fare (₦)", secondary_y=True)

        st.plotly_chart(fig, use_container_width=True)

    # Payment methods
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Payment Methods")
        payment_analysis = get_cached_payment_analysis(analytics_id)
        if payment_analysis is None:
            payment_analysis = analytics.get_payment_analysis()

        if not payment_analysis.empty:
            fig = px.pie(
                values=payment_analysis['count'],
                names=payment_analysis.index,
                title="Payment Method Distribution"
            )
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Revenue by Payment Method")
        if not payment_analysis.empty:
            fig = px.bar(
                payment_analysis.reset_index(),
                x='payment_method',
                y='total_amount',
                title="Revenue by Payment Method",
                labels={'total_amount': 'Revenue (₦)', 'payment_method': 'Payment Method'}
            )
            st.plotly_chart(fig, use_container_width=True)

    # Fare distribution
    st.subheader("Fare Distribution")
    fare_dist = get_cached_fare_distribution(analytics_id)
    if fare_dist is None:
        fare_dist = analytics.get_fare_distribution()

    if fare_dist:
        col1, col2 = st.columns(2)

        with col1:
            st.write("**Fare Statistics**")
            st.write(f"- Min: ₦{fare_dist['min']:,.0f}")
            st.write(f"- Max: ₦{fare_dist['max']:,.0f}")
            st.write(f"- Mean: ₦{fare_dist['mean']:,.0f}")
            st.write(f"- Median: ₦{fare_dist['median']:,.0f}")
            st.write(f"- Std Dev: ₦{fare_dist['std']:,.0f}")

        with col2:
            st.write("**Percentiles**")
            for pct, value in fare_dist['percentiles'].items():
                st.write(f"- {pct}: ₦{value:,.0f}")

    # Fare histogram
    completed = trips[trips['ride_status'] == 'completed']
    if 'fare' in completed.columns:
        fares = completed['fare'].dropna()
        fig = px.histogram(
            fares,
            nbins=50,
            title="Fare Distribution",
            labels={'value': 'Fare (₦)', 'count': 'Frequency'}
        )
        st.plotly_chart(fig, use_container_width=True)


def show_user_behavior(analytics, trips, users):
    """Display user behavior analytics page"""
    st.header("👥 User Behavior Analytics")

    analytics_id = st.session_state.get('analytics_id', 0)

    # Retention metrics
    st.subheader("Retention Metrics")
    retention = get_cached_retention_metrics(analytics_id)
    if retention is None:
        retention = analytics.get_retention_metrics()

    if retention:
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Total Riders", f"{retention['total_riders']:,}")

        with col2:
            st.metric("Active Riders", f"{retention['active_riders']:,}")

        with col3:
            st.metric("Churned Riders", f"{retention['churned_riders']:,}")

        with col4:
            st.metric("Churn Rate", f"{retention['churn_rate']:.1f}%")

        col1, col2 = st.columns(2)

        with col1:
            st.metric("Avg Lifetime (days)", f"{retention['avg_lifetime_days']:.0f}")

        with col2:
            st.metric("Avg Trips/Rider", f"{retention['avg_trips_per_rider']:.1f}")

    st.markdown("---")

    # Top performers
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Top 20 Drivers")
        driver_perf = get_cached_driver_performance(analytics_id, top_n=20)
        if driver_perf is None:
            driver_perf = analytics.get_driver_performance(top_n=20)

        if not driver_perf.empty:
            display_df = driver_perf.reset_index()[['driver_name', 'total_trips', 'completion_rate', 'total_revenue']]
            display_df['total_revenue'] = display_df['total_revenue'].apply(lambda x: f"₦{x:,.0f}")
            display_df['completion_rate'] = display_df['completion_rate'].apply(lambda x: f"{x:.1f}%")
            st.dataframe(display_df, hide_index=True, use_container_width=True)

    with col2:
        st.subheader("Top 20 Riders")
        rider_behavior = get_cached_rider_behavior(analytics_id, top_n=20)
        if rider_behavior is None:
            rider_behavior = analytics.get_rider_behavior(top_n=20)

        if not rider_behavior.empty:
            display_df = rider_behavior.reset_index()[['rider_name', 'total_trips', 'total_spent', 'preferred_payment']]
            display_df['total_spent'] = display_df['total_spent'].apply(lambda x: f"₦{x:,.0f}")
            st.dataframe(display_df, hide_index=True, use_container_width=True)

    # User segmentation
    st.subheader("User Segmentation")

    with st.spinner("Performing user segmentation..."):
        segments = get_cached_user_segments(analytics_id, n_clusters=4)
        if segments is None:
            segments = analytics.segment_users_by_activity(n_clusters=4)

    if not segments.empty:
        segment_summary = segments.groupby('segment_label').agg({
            'trip_count': ['mean', 'count'],
            'total_spent': 'mean',
            'avg_fare': 'mean',
            'completion_rate': 'mean'
        }).round(2)

        st.write("**Segment Summary**")
        st.dataframe(segment_summary, use_container_width=True)

        # Visualization
        fig = px.scatter(
            segments.reset_index(),
            x='trip_count',
            y='total_spent',
            color='segment_label',
            size='avg_fare',
            hover_data=['completion_rate'],
            title="User Segments: Trip Count vs Total Spend",
            labels={
                'trip_count': 'Number of Trips',
                'total_spent': 'Total Spent (₦)',
                'segment_label': 'Segment'
            }
        )
        st.plotly_chart(fig, use_container_width=True)


def show_geographic_insights(analytics, trips):
    """Display geographic insights page"""
    st.header("📍 Geographic Insights")

    analytics_id = st.session_state.get('analytics_id', 0)

    # Area analysis
    st.subheader("Top Areas by Trip Volume")
    area_stats = get_cached_area_analysis(analytics_id)
    if area_stats is None:
        area_stats = analytics.get_area_analysis()

    if not area_stats.empty:
        top_areas = area_stats.head(20)

        fig = go.Figure()
        fig.add_trace(go.Bar(
            y=top_areas.index,
            x=top_areas['total_requests'],
            orientation='h',
            name='Total Requests'
        ))

        fig.update_layout(
            xaxis_title="Number of Requests",
            yaxis_title="Area",
            height=600
        )
        st.plotly_chart(fig, use_container_width=True)

    # LGA analysis
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("LGA Distribution")
        lga_stats = get_cached_lga_analysis(analytics_id)
        if lga_stats is None:
            lga_stats = analytics.get_lga_analysis()

        if not lga_stats.empty:
            top_lga = lga_stats.head(10)
            fig = px.pie(
                values=top_lga['total_requests'],
                names=top_lga.index,
                title="Top 10 LGAs by Request Volume"
            )
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Revenue by LGA")
        if not lga_stats.empty:
            top_lga = lga_stats.head(10)
            fig = px.bar(
                x=top_lga.index,
                y=top_lga['total_revenue'],
                title="Top 10 LGAs by Revenue",
                labels={'x': 'LGA', 'y': 'Revenue (₦)'}
            )
            st.plotly_chart(fig, use_container_width=True)

    # Hotspot map
    st.subheader("Ride Request Hotspots")

    hotspots = get_cached_hotspot_locations(analytics_id, top_n=100)
    if hotspots is None:
        hotspots = analytics.get_hotspot_locations(top_n=100)

    if not hotspots.empty:
        # Clean data
        hotspots_clean = hotspots.dropna(subset=['start_lat', 'start_lon'])
        hotspots_clean = hotspots_clean[
            (hotspots_clean['start_lat'] != 0) &
            (hotspots_clean['start_lon'] != 0)
        ]

        if len(hotspots_clean) > 0:
            # Create map centered on Lagos
            lagos_center = [6.5244, 3.3792]
            m = folium.Map(location=lagos_center, zoom_start=11)

            # Add hotspots
            for idx, row in hotspots_clean.iterrows():
                folium.CircleMarker(
                    location=[row['start_lat'], row['start_lon']],
                    radius=min(row['request_count'] / 10, 20),
                    popup=f"{row['location'][:50]}<br>Requests: {row['request_count']}",
                    color='red',
                    fill=True,
                    fillColor='red',
                    fillOpacity=0.6
                ).add_to(m)

            folium_static(m, width=1200, height=600)

    # Route efficiency
    st.subheader("Route Efficiency Analysis")
    route_eff = get_cached_route_efficiency(analytics_id)
    if route_eff is None:
        route_eff = analytics.get_route_efficiency()

    if route_eff:
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Avg Estimated Distance", f"{route_eff['avg_estimated_distance']:.2f} km")

        with col2:
            st.metric("Avg Actual Distance", f"{route_eff['avg_actual_distance']:.2f} km")

        with col3:
            st.metric("Avg Variance", f"{route_eff['avg_variance']:.2f} km")


def show_transit_patterns(analytics, trips, users):
    """Display transit pattern analytics - users with similar routes and timing"""
    st.header("🔄 Transit Pattern Analytics")

    analytics_id = st.session_state.get('analytics_id', 0)

    # ============ PRIMARY: CORRIDOR COMMUTERS (moved to top) ============
    st.subheader("🎯 Corridor Commuters (To & Fro, Morning & Evening)")
    st.markdown("""
    Users who travel **both directions** on a corridor during **morning AND evening** hours.
    These are your most consistent commuters - ideal targets for EV services.
    """)

    with st.spinner("Analyzing bidirectional commuter patterns..."):
        try:
            commuter_corridors = get_cached_commuter_corridors(analytics_id, min_users=3, min_trips=2)
            if commuter_corridors is None:
                commuter_corridors = analytics.get_all_commuter_corridors(min_users=3, min_trips=2)

            if commuter_corridors is not None and not commuter_corridors.empty:
                st.write(f"**Found {len(commuter_corridors)} corridors with regular commuters**")

                # Show corridor summary
                corridor_display = commuter_corridors.copy()
                corridor_display['total_spent'] = corridor_display['total_spent'].apply(lambda x: f"₦{x:,.0f}")
                corridor_display['avg_trips_per_user'] = corridor_display['avg_trips_per_user'].apply(lambda x: f"{x:.1f}")

                st.dataframe(
                    corridor_display[['corridor', 'total_users', 'total_trips', 'avg_trips_per_user', 'total_spent']],
                    hide_index=True, use_container_width=True
                )

                st.markdown("---")

                # Corridor selector
                st.write("**Select a corridor to view commuters with contact details:**")

                selected_corridor = st.selectbox(
                    "Choose Corridor",
                    options=commuter_corridors['corridor'].tolist(),
                    format_func=lambda x: f"{x} ({commuter_corridors[commuter_corridors['corridor']==x]['total_users'].values[0]} users)",
                    key="transit_corridor_select"
                )

                if selected_corridor:
                    with st.spinner(f"Loading users for {selected_corridor}..."):
                        corridor_users = get_cached_corridor_users(analytics_id, selected_corridor, min_trips=2)
                        if corridor_users is None:
                            corridor_users = analytics.get_corridor_users_with_contacts(selected_corridor, min_trips=2)

                    if corridor_users is not None and not corridor_users.empty:
                        st.write(f"**{len(corridor_users)} commuters on this corridor:**")

                        # Format for display
                        display_users = corridor_users.copy()
                        if 'total_spent' in display_users.columns:
                            display_users['total_spent'] = display_users['total_spent'].apply(lambda x: f"₦{x:,.0f}")

                        st.dataframe(display_users, hide_index=True, use_container_width=True)

                        # Excel download
                        excel_buffer = io.BytesIO()
                        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                            corridor_users.to_excel(writer, sheet_name='Commuters', index=False)
                        excel_buffer.seek(0)

                        safe_filename = selected_corridor.replace(' ', '_').replace('/', '-').replace('↔', 'to')[:50]

                        col1, col2 = st.columns(2)
                        with col1:
                            st.download_button(
                                label=f"📥 Download {len(corridor_users)} users as Excel",
                                data=excel_buffer,
                                file_name=f"commuters_{safe_filename}.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                key="transit_download_single"
                            )

                        with col2:
                            if st.button("📥 Generate ALL Corridors Excel", key="transit_download_all_btn"):
                                with st.spinner("Generating..."):
                                    all_buffer = io.BytesIO()
                                    with pd.ExcelWriter(all_buffer, engine='openpyxl') as writer:
                                        for corridor in commuter_corridors['corridor'].tolist():
                                            users_df = analytics.get_corridor_users_with_contacts(corridor, min_trips=2)
                                            if users_df is not None and not users_df.empty:
                                                sheet_name = corridor[:28].replace('/', '-').replace('↔', '-')
                                                users_df.to_excel(writer, sheet_name=sheet_name, index=False)
                                    all_buffer.seek(0)
                                    st.download_button(
                                        label="📥 Download Now",
                                        data=all_buffer,
                                        file_name="all_corridor_commuters.xlsx",
                                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                        key="transit_download_all_file"
                                    )
                    else:
                        st.info("No qualifying commuters found for this corridor")
            else:
                st.info("No corridors with regular morning+evening commuters found")

        except Exception as e:
            st.error(f"Error analyzing corridors: {str(e)}")
            import traceback
            st.code(traceback.format_exc())

    st.markdown("---")
    st.markdown("---")

    # ============ SECONDARY: PATTERN OVERVIEW ============
    st.subheader("📊 Pattern Overview")

    with st.spinner("Analyzing transit patterns..."):
        summary = get_cached_transit_summary(analytics_id)
        if summary is None:
            summary = analytics.get_transit_pattern_summary()

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Users Analyzed", f"{summary.get('total_users_analyzed', 0):,}")

    with col2:
        st.metric("Identified Commuters", f"{summary.get('identified_commuters', 0):,}")

    with col3:
        if summary.get('total_users_analyzed', 0) > 0:
            commuter_pct = (summary.get('identified_commuters', 0) / summary.get('total_users_analyzed', 1)) * 100
            st.metric("Commuter Rate", f"{commuter_pct:.1f}%")

    st.markdown("---")

    # Time Pattern Distribution
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Time-of-Day Patterns")
        time_dist = summary.get('time_pattern_distribution', {})
        if time_dist:
            fig = px.pie(
                values=list(time_dist.values()),
                names=list(time_dist.keys()),
                title="User Distribution by Primary Travel Time"
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No time pattern data available")

    with col2:
        st.subheader("Commuter Types")
        commuter_dist = summary.get('commuter_type_distribution', {})
        if commuter_dist:
            fig = px.bar(
                x=list(commuter_dist.keys()),
                y=list(commuter_dist.values()),
                labels={'x': 'Commuter Type', 'y': 'Number of Users'},
                title="Distribution of Commuter Types"
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No commuter data available")

    st.markdown("---")

    # Top Transit Corridors
    st.subheader("Top Transit Corridors")
    st.markdown("Most popular area-to-area routes (e.g., Lekki Phase 1 → Victoria Island)")

    with st.spinner("Analyzing transit corridors..."):
        try:
            analytics_id = st.session_state.get('analytics_id', 0)
            corridors = get_cached_transit_corridors(analytics_id, top_n=20)
            if corridors is None:
                corridors = analytics.get_transit_corridors(top_n=20)

            if not corridors.empty:
                fig = px.bar(
                    corridors.reset_index(),
                    y='corridor',
                    x='unique_users',
                    orientation='h',
                    title="Top 20 Transit Corridors by User Count",
                    labels={'corridor': 'Corridor', 'unique_users': 'Unique Users'}
                )
                fig.update_layout(height=600, yaxis={'categoryorder': 'total ascending'})
                st.plotly_chart(fig, use_container_width=True)
        except Exception as e:
            st.error(f"Error loading corridors: {str(e)}")

    st.markdown("---")

    # Corridor Commuters Table
    st.subheader("Users with Corridor Patterns")
    st.markdown("Users with consistent area-to-area travel patterns (3+ trips, 30%+ consistency)")

    with st.spinner("Identifying corridor patterns..."):
        try:
            commuters = analytics.identify_corridor_commuters(min_trips=3, consistency_threshold=0.3)

            if not commuters.empty:
                col1, col2 = st.columns([1, 3])

                with col1:
                    st.write("**Pattern Stats**")
                    st.write(f"- Users with patterns: {commuters['rider_id'].nunique():,}")
                    st.write(f"- Avg Corridor Trips: {commuters['corridor_trips'].mean():.1f}")
                    st.write(f"- Avg Total Spend: ₦{commuters['total_spent'].mean():,.0f}")
                    st.write(f"- Avg Consistency: {commuters['consistency'].mean()*100:.1f}%")

                with col2:
                    # Show top corridor users
                    display_commuters = commuters.head(30).copy()
                    display_commuters['consistency'] = display_commuters['consistency'].apply(lambda x: f"{x*100:.1f}%")
                    display_commuters['corridor'] = display_commuters['corridor'].str[:50]
                    display_commuters['total_spent'] = display_commuters['total_spent'].apply(lambda x: f"₦{x:,.0f}")

                    st.dataframe(
                        display_commuters[['rider_id', 'corridor', 'corridor_trips', 'consistency', 'commuter_type']],
                        hide_index=True, use_container_width=True
                    )
            else:
                st.info("No corridor patterns identified")
        except Exception as e:
            st.error(f"Error identifying patterns: {str(e)}")

    st.markdown("---")

    # Transit Pattern Clustering
    st.subheader("Transit Pattern Segments")
    st.markdown("Users clustered by similar routes, locations, and travel times")

    n_clusters = st.slider("Number of segments", min_value=3, max_value=8, value=5)

    with st.spinner("Clustering users by transit patterns..."):
        try:
            result = analytics.cluster_users_by_transit_patterns(n_clusters=n_clusters, min_trips=3)

            if isinstance(result, tuple) and len(result) == 2:
                user_clusters, cluster_profiles = result

                # Show cluster profiles
                st.write("**Segment Profiles**")

                profile_display = cluster_profiles[['label', 'user_count', 'avg_trips', 'avg_spent', 'avg_distance', 'route_consistency']].copy()
                profile_display['avg_spent'] = profile_display['avg_spent'].apply(lambda x: f"₦{x:,.0f}")
                profile_display['avg_distance'] = profile_display['avg_distance'].apply(lambda x: f"{x:.1f} km")
                profile_display['route_consistency'] = profile_display['route_consistency'].apply(lambda x: f"{x*100:.1f}%")
                profile_display['avg_trips'] = profile_display['avg_trips'].apply(lambda x: f"{x:.1f}")

                st.dataframe(profile_display, hide_index=True, use_container_width=True)

                # Visualization
                col1, col2 = st.columns(2)

                with col1:
                    fig = px.pie(
                        cluster_profiles,
                        values='user_count',
                        names='label',
                        title="User Distribution by Transit Segment"
                    )
                    st.plotly_chart(fig, use_container_width=True)

                with col2:
                    fig = px.scatter(
                        user_clusters.reset_index(),
                        x='trip_count',
                        y='avg_distance',
                        color='transit_segment',
                        size='total_spent',
                        hover_data=['typical_hour', 'route_consistency'],
                        title="Transit Segments: Trips vs Distance",
                        labels={
                            'trip_count': 'Number of Trips',
                            'avg_distance': 'Avg Distance (km)',
                            'transit_segment': 'Segment'
                        }
                    )
                    st.plotly_chart(fig, use_container_width=True)

                # Detailed segment view
                st.write("**Explore Segment Details**")
                selected_segment = st.selectbox(
                    "Select a segment to view users",
                    options=cluster_profiles['label'].tolist()
                )

                segment_users = user_clusters[user_clusters['transit_segment'] == selected_segment].head(50)
                if not segment_users.empty:
                    display_segment = segment_users.reset_index()[['rider_id', 'trip_count', 'total_spent', 'avg_distance', 'typical_hour', 'route_consistency']]
                    display_segment['total_spent'] = display_segment['total_spent'].apply(lambda x: f"₦{x:,.0f}")
                    display_segment['avg_distance'] = display_segment['avg_distance'].apply(lambda x: f"{x:.1f} km")
                    display_segment['route_consistency'] = display_segment['route_consistency'].apply(lambda x: f"{x*100:.1f}%")
                    st.dataframe(display_segment, hide_index=True, use_container_width=True)

        except Exception as e:
            st.error(f"Error clustering users: {str(e)}")
            st.info("Try adjusting the number of segments or loading more data")

    # Find Similar Users
    st.subheader("Find Similar Users")
    st.markdown("Enter a user ID to find other users with similar transit patterns")

    # Get sample user IDs
    sample_ids = trips['rider_id'].dropna().unique()[:100]

    col1, col2 = st.columns([2, 1])

    with col1:
        user_id_input = st.text_input(
            "Enter Rider ID",
            placeholder="e.g., " + str(sample_ids[0]) if len(sample_ids) > 0 else "Enter rider ID"
        )

    with col2:
        top_n = st.number_input("Number of similar users", min_value=5, max_value=50, value=10)

    if user_id_input:
        with st.spinner("Finding similar users..."):
            similar_users = analytics.find_similar_users(user_id_input, top_n=top_n)

        if not similar_users.empty:
            st.write(f"**Users with similar transit patterns to {user_id_input}:**")

            display_similar = similar_users.reset_index()
            display_similar['similarity_score'] = display_similar['similarity_score'].apply(lambda x: f"{x:.3f}")
            display_similar['total_distance'] = display_similar['total_distance'].apply(lambda x: f"{x:.1f} km")

            st.dataframe(display_similar, hide_index=True, use_container_width=True)
        else:
            st.warning("No similar users found or user ID not found in data")

    st.markdown("---")

    # Popular Routes by Time
    st.subheader("Popular Routes by Time of Day")

    with st.spinner("Analyzing routes by time..."):
        route_patterns = analytics.get_user_route_patterns(min_trips=2)

    if not route_patterns.empty:
        # Group by time period
        time_route_counts = route_patterns.groupby('time_period').agg({
            'rider_id': 'nunique',
            'trip_count': 'sum',
            'route': 'count'
        }).rename(columns={
            'rider_id': 'unique_users',
            'trip_count': 'total_trips',
            'route': 'unique_routes'
        })

        col1, col2 = st.columns(2)

        with col1:
            fig = px.bar(
                time_route_counts.reset_index(),
                x='time_period',
                y='unique_users',
                title="Users by Primary Travel Time",
                labels={'time_period': 'Time Period', 'unique_users': 'Number of Users'}
            )
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            # Top routes per time period
            selected_time = st.selectbox(
                "Select time period to see top routes",
                options=route_patterns['time_period'].unique()
            )

            time_routes = route_patterns[route_patterns['time_period'] == selected_time]
            top_routes = time_routes.groupby('route')['trip_count'].sum().nlargest(10)

            if not top_routes.empty:
                fig = px.bar(
                    x=top_routes.values,
                    y=[r[:40] + '...' if len(r) > 40 else r for r in top_routes.index],
                    orientation='h',
                    title=f"Top Routes - {selected_time}",
                    labels={'x': 'Trip Count', 'y': 'Route'}
                )
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)


if __name__ == "__main__":
    main()
