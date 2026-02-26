# Lagos Ride-Hailing Data Analysis Engine

A comprehensive interactive analytics dashboard for analyzing ride-hailing data from Lagos. This system provides deep insights across trip analytics, financial metrics, user behavior, and geographic patterns.

## Features

### 🚕 Trip Analytics
- Real-time trip trends and patterns
- Peak hours and day-of-week analysis
- Popular routes identification
- Cancellation analysis and patterns
- Completion rate tracking

### 💰 Financial Metrics
- Revenue tracking and trends
- Fare distribution analysis
- Payment method breakdown
- Revenue per kilometer calculations
- Outstanding settlements monitoring

### 👥 User Behavior Analytics
- Driver performance metrics
- Rider behavior patterns
- User segmentation with ML clustering
- Retention and churn analysis
- Top performers identification

### 📍 Geographic Insights
- Interactive hotspot maps
- Area-wise demand analysis
- LGA (Local Government Area) statistics
- Route efficiency metrics
- Coverage gap identification

## Technology Stack

- **Data Processing**: Pandas, Dask (for large-scale processing)
- **Visualization**: Plotly, Streamlit
- **Mapping**: Folium, GeoPandas
- **Machine Learning**: Scikit-learn (user segmentation)
- **Statistical Analysis**: SciPy, NumPy

## Installation

1. **Install Python dependencies**:
```bash
pip install -r requirements.txt
```

2. **Verify installation**:
```bash
python -c "import streamlit; import pandas; import plotly; print('All packages installed successfully!')"
```

## Usage

### Quick Start

1. **Launch the dashboard**:
```bash
streamlit run dashboard.py
```

2. **Access the dashboard**:
   - Open your browser to `http://localhost:8501`
   - The dashboard will automatically load

3. **Choose your dataset size**:
   - Start with "Sample 10%" for quick exploration
   - Use "Full Dataset" for complete analysis (may take 1-2 minutes to load)

### Data Loading Options

The dashboard provides flexible data loading:
- **Full Dataset**: All 1.4GB of trip data (~1-2 min load time)
- **Sample 50%**: Half the dataset for balanced performance
- **Sample 10%**: Quick loading for exploration
- **Sample 1%**: Very fast loading for testing

### Dashboard Navigation

Navigate through five main sections:

1. **Overview**: High-level KPIs and trends
2. **Trip Analytics**: Detailed trip patterns and behavior
3. **Financial Metrics**: Revenue analysis and fare distributions
4. **User Behavior**: Driver/rider analytics and segmentation
5. **Geographic Insights**: Maps and location-based analysis

## Module Documentation

### `data_loader.py`
Handles efficient loading of large CSV files.

```python
from data_loader import RideDataLoader

loader = RideDataLoader()
trips, users = loader.load_all(sample_frac=0.1)  # Load 10% sample
```

### `analytics.py`
Provides comprehensive analytics functions.

```python
from analytics import RideAnalytics

analytics = RideAnalytics(trips, users)

# Get trip overview
overview = analytics.get_trip_overview()

# Get revenue metrics
revenue = analytics.get_revenue_overview()

# Segment users
segments = analytics.segment_users_by_activity(n_clusters=4)
```

## Data Structure

### Trip Requests Data
- **Files**: `lagosride.trip_requests.export*.csv` (14 files)
- **Size**: ~1.4GB total
- **Key Fields**: trip_ref, ride_status, driver/rider info, locations, fares, timestamps

### Users Data
- **Files**: `lagosride.users*.csv` (2 files)
- **Size**: ~380MB total
- **Key Fields**: user_type, contact info, banking details, referral codes

## Advanced Usage

### Custom Analysis

Create custom analyses using the analytics module:

```python
from data_loader import RideDataLoader
from analytics import RideAnalytics

# Load data
loader = RideDataLoader()
trips, users = loader.load_all()

# Initialize analytics
analytics = RideAnalytics(trips, users)

# Custom analysis
peak_hours = analytics.get_peak_hours()
top_drivers = analytics.get_driver_performance(top_n=100)
hotspots = analytics.get_hotspot_locations(top_n=50)
```

### Export Data

Export analysis results for further processing:

```python
# Export top routes to Excel
popular_routes = analytics.get_popular_routes(top_n=100)
popular_routes.to_excel('popular_routes.xlsx')

# Export driver performance
driver_stats = analytics.get_driver_performance(top_n=500)
driver_stats.to_csv('driver_performance.csv')
```

## Performance Tips

1. **Start with samples**: Use sample data for initial exploration
2. **Use caching**: The dashboard caches loaded data automatically
3. **Filter data**: Apply filters in the dashboard to focus on specific time periods
4. **Export results**: Export interesting findings for offline analysis

## Troubleshooting

### Memory Issues
If you encounter memory errors with the full dataset:
```bash
# Use sample data or increase Python memory limit
export PYTHONHASHSEED=0
streamlit run dashboard.py
```

### Slow Loading
- Start with 10% sample
- Close other applications
- Use SSD storage for data files

### Import Errors
```bash
# Reinstall dependencies
pip install -r requirements.txt --upgrade
```

## Dataset Information

- **Date Range**: 2021-2022
- **Location**: Lagos, Nigeria
- **Total Trips**: ~1.5 million records
- **Unique Drivers**: Thousands
- **Unique Riders**: Hundreds of thousands

## Future Enhancements

Potential additions:
- Real-time data streaming
- Predictive demand forecasting
- Driver-rider matching optimization
- Surge pricing analysis
- Route optimization algorithms
- Mobile-responsive design

## License

This analytics engine is for internal use and analysis purposes.

## Support

For issues or questions:
1. Check the troubleshooting section
2. Review module documentation
3. Test with sample data first
