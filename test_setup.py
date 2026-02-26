"""
Test Setup Script
Verifies that all components are working correctly
"""

import sys
import warnings
warnings.filterwarnings('ignore')


def test_imports():
    """Test that all required packages can be imported"""
    print("Testing package imports...")

    required_packages = [
        ('pandas', 'Pandas'),
        ('numpy', 'NumPy'),
        ('streamlit', 'Streamlit'),
        ('plotly', 'Plotly'),
        ('folium', 'Folium'),
        ('sklearn', 'Scikit-learn'),
        ('scipy', 'SciPy'),
        ('dask', 'Dask')
    ]

    failed = []

    for package, name in required_packages:
        try:
            __import__(package)
            print(f"  ✓ {name}")
        except ImportError:
            print(f"  ✗ {name} - NOT INSTALLED")
            failed.append(name)

    if failed:
        print(f"\n⚠️  Missing packages: {', '.join(failed)}")
        print("Install with: pip install -r requirements.txt")
        return False

    print("\n✅ All packages installed successfully!\n")
    return True


def test_data_loader():
    """Test the data loader module"""
    print("Testing data loader...")

    try:
        from data_loader import RideDataLoader

        loader = RideDataLoader()
        print("  ✓ Data loader initialized")

        # Test loading a small sample
        print("  Loading 1% sample of trip data...")
        trips, users = loader.load_all(sample_frac=0.01)

        print(f"  ✓ Loaded {len(trips):,} trips")
        print(f"  ✓ Loaded {len(users):,} users")

        # Test summary
        summary = loader.get_data_summary()
        print(f"  ✓ Generated data summary")

        print("\n✅ Data loader working correctly!\n")
        return True

    except Exception as e:
        print(f"\n❌ Data loader test failed: {e}\n")
        return False


def test_analytics():
    """Test the analytics module"""
    print("Testing analytics module...")

    try:
        from data_loader import RideDataLoader
        from analytics import RideAnalytics

        # Load small sample
        loader = RideDataLoader()
        trips, users = loader.load_all(sample_frac=0.01)

        # Initialize analytics
        analytics = RideAnalytics(trips, users)
        print("  ✓ Analytics engine initialized")

        # Test various analytics functions
        overview = analytics.get_trip_overview()
        print(f"  ✓ Trip overview: {overview['total_trips']:,} trips")

        revenue = analytics.get_revenue_overview()
        print(f"  ✓ Revenue overview: ₦{revenue['total_revenue']:,.0f}")

        peak_hours = analytics.get_peak_hours()
        print(f"  ✓ Peak hours analysis: {len(peak_hours)} hours")

        driver_perf = analytics.get_driver_performance(top_n=10)
        print(f"  ✓ Driver performance: Top {len(driver_perf)} drivers")

        area_stats = analytics.get_area_analysis()
        print(f"  ✓ Area analysis: {len(area_stats)} areas")

        print("\n✅ Analytics module working correctly!\n")
        return True

    except Exception as e:
        print(f"\n❌ Analytics test failed: {e}\n")
        import traceback
        traceback.print_exc()
        return False


def test_data_files():
    """Test that data files exist"""
    print("Testing data files...")

    from pathlib import Path

    data_dir = Path(".")
    trip_files = list(data_dir.glob("lagosride.trip_requests.export*.csv"))
    user_files = list(data_dir.glob("lagosride.users*.csv"))

    if not trip_files:
        print("  ✗ No trip request files found")
        return False

    if not user_files:
        print("  ✗ No user files found")
        return False

    print(f"  ✓ Found {len(trip_files)} trip request files")
    print(f"  ✓ Found {len(user_files)} user files")

    # Check file sizes
    total_size = sum(f.stat().st_size for f in trip_files + user_files)
    print(f"  ✓ Total data size: {total_size / 1024**3:.2f} GB")

    print("\n✅ All data files found!\n")
    return True


def main():
    """Run all tests"""
    print("="*60)
    print("Lagos Ride-Hailing Analytics - Setup Test")
    print("="*60)
    print()

    results = []

    # Test data files
    results.append(("Data Files", test_data_files()))

    # Test imports
    results.append(("Package Imports", test_imports()))

    # Test data loader
    results.append(("Data Loader", test_data_loader()))

    # Test analytics
    results.append(("Analytics Module", test_analytics()))

    # Summary
    print("="*60)
    print("TEST SUMMARY")
    print("="*60)

    all_passed = True
    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{test_name:20s}: {status}")
        if not passed:
            all_passed = False

    print("="*60)

    if all_passed:
        print("\n🎉 All tests passed! You're ready to use the dashboard.")
        print("\nRun the dashboard with:")
        print("  streamlit run dashboard.py")
        return 0
    else:
        print("\n⚠️  Some tests failed. Please fix the issues above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
