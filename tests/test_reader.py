import pytest
import polars as pl
from polars.testing import assert_frame_equal
from src.reader import CSVTelemetryReader

# ==========================================
# FIXTURES
# ==========================================
@pytest.fixture
def bouncer():
    """
    Creates an instance of CSVTelemetryReader without triggering __init__.
    This isolates the test from file I/O operations.
    """
    return CSVTelemetryReader.__new__(CSVTelemetryReader)

# ==========================================
# TESTS
# ==========================================
def test_sanitize_batch_drops_corrupted_rows(bouncer):
    # 1. ARRANGE: Create a "dirty" DataFrame that mimics project errors.
    dirty_data = pl.DataFrame({
        'timestamp': ['2026-04-24T10:00Z', '2026-04-24T10:01Z', '2026-04-24T10:02Z', 'TIME_STAMP_MALFORMED', '12', '2026-04-24T10:05Z', '2026-04-24T10:06Z'], 
        'sensor_id': ['TEMP-01', None, 'TEMP-03', 'TEMP-04', 'TEMP-05', '13', 'TEMP-07'],     
        'value': ['25.5', '26.0', 'SENSOR_BROKEN', '28.5', '29.0', '24.0', '23.5'],               
        'priority': ['HIGH', 'LOW', 'HIGH', 'LOW', 'HIGH', 'LOW', '12']    
    }, schema={"timestamp": pl.Utf8, "sensor_id": pl.Utf8, "value": pl.Utf8, "priority": pl.Utf8})
    
    # 2. ACT: Pass the dirty data through our function
    cleaned_data = bouncer._sanitize_batch(dirty_data)
    
    # 3. ASSERT: Polars strict schema safely interprets "13" as a valid sensor ID string
    expected_data = pl.DataFrame({
        'timestamp': ['2026-04-24T10:00Z', '2026-04-24T10:05Z'],
        'sensor_id': ['TEMP-01', '13'],
        'value': [25.5, 24.0],
        'priority': ['HIGH', 'LOW']
    }, schema={"timestamp": pl.Utf8, "sensor_id": pl.Utf8, "value": pl.Float64, "priority": pl.Utf8})
    
    assert_frame_equal(cleaned_data, expected_data)

def test_sanitize_batch_handles_missing_columns(bouncer):
    # 1. ARRANGE: A DataFrame completely missing the 'priority' column
    missing_col_data = pl.DataFrame({
        'timestamp': ['2026-04-24T10:00Z'],
        'sensor_id': ['TEMP-01'],
        'value': ['25.5']
    }, schema={"timestamp": pl.Utf8, "sensor_id": pl.Utf8, "value": pl.Utf8})

    # 2. ACT:
    cleaned_data = bouncer._sanitize_batch(missing_col_data)

    # 3. ASSERT: The row should survive, and priority should be set to 'LOW'
    assert cleaned_data.height > 0, "Data should not be empty"
    assert 'priority' in cleaned_data.columns, "Priority column was not created"
    assert cleaned_data['priority'][0] == 'LOW', "Missing priority did not default to LOW"