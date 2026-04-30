import pytest
import pandas as pd
import numpy as np
from pandas.testing import assert_frame_equal
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
    # 1. ARRANGE: Create a "dirty" DataFrame that mimics 2 project errors
    dirty_data = pd.DataFrame({
        'timestamp': ['2026-04-24T10:00Z', '2026-04-24T10:01Z', '2026-04-24T10:02Z', 'TIME_STAMP_MALFORMED', 12, '2026-04-24T10:05Z', '2026-04-24T10:06Z'], 
        # Malformed timestamp + wrong data type (int instead of string) 
        'sensor_id': ['TEMP-01', pd.NA, 'TEMP-03', 'TEMP-04', 'TEMP-05', 13, 'TEMP-07'],     
        # Missing mandatory field (Schema Error)
        'value': [25.5, 26.0, 'SENSOR_BROKEN', 28.5, 29.0, 24.0, 23.5],               
        # String instead of float (Type Error)
        'priority': ['HIGH', 'LOW', 'HIGH', 'LOW', 'HIGH', 'LOW', 12]    
        # Wrong data type (int instead of string)         
    })
    
    # 2. ACT: Pass the dirty data through our function
    cleaned_data = bouncer._sanitize_batch(dirty_data)
    
    # 3. ASSERT: Define exactly what the resulting DataFrame MUST look like.
    # Only Row 0 is perfectly valid. All others should have been assassinated by the Bouncer.
    expected_data = pd.DataFrame({
        'timestamp': ['2026-04-24T10:00Z'],
        'sensor_id': ['TEMP-01'],
        'value': [25.5],
        'priority': ['HIGH']
    }, index=[0]) # Keep the original Pandas index (0) for the surviving row
    
    # assert_frame_equal is strict: it checks values, data types, AND column names
    assert_frame_equal(cleaned_data, expected_data)

def test_sanitize_batch_handles_missing_columns(bouncer):
    # 1. ARRANGE: A DataFrame completely missing the 'priority' column
    missing_col_data = pd.DataFrame({
        'timestamp': ['2026-04-24T10:00Z'],
        'sensor_id': ['TEMP-01'],
        'value': [25.5]
    })
    
    # 2. ACT:
    cleaned_data = bouncer._sanitize_batch(missing_col_data)
    
    # 3. ASSERT: Because a mandatory column is missing, the ENTIRE batch should be empty
    assert cleaned_data.empty is True
