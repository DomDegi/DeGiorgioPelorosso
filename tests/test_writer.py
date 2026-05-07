import os
import tempfile
import pytest
import polars as pl
from src.writer import CSVOutputWriter

@pytest.fixture
def temp_output_dir():
    """Fixture to create a temporary directory for output files during testing."""
    with tempfile.TemporaryDirectory() as tmpdirname:
        yield tmpdirname

def test_writer_clean_start(temp_output_dir):
    """
    EDGE CASE: Ensure idempotency. If an old valid_data.csv exists from a 
    previous crashed run, clean_start=True must delete it.
    """
    valid_path = os.path.join(temp_output_dir, "valid_data.csv")
    
    # Simulate an old leftover file
    with open(valid_path, 'w') as f:
        f.write("OLD CORRUPTED DATA")
        
    # Instantiate writer with clean_start
    writer = CSVOutputWriter(output_dir=temp_output_dir)
    
    # The old file should have been deleted
    assert not os.path.exists(valid_path), "Writer did not remove old files on clean start"

def test_write_valid_batch_determinism(temp_output_dir):
    """
    EDGE CASE: CI/CD Determinism. The writer MUST sort the sensors alphabetically
    to guarantee the output string is identical regardless of the input row order.
    """
    writer = CSVOutputWriter(output_dir=temp_output_dir)
    
    # Input with unsorted sensors (TEMP comes before ACCEL in the dataframe)
    data = pl.DataFrame({
        'timestamp': ['2026-04-14T08:00:00Z', '2026-04-14T08:00:00Z'],
        'sensor_id': ['TEMP-01', 'ACCEL-02'],
        'value': [25.5, 1.2]
    })
    
    writer.write_valid_batch(data)
    
    with open(writer.valid_path, 'r') as f:
        content = f.read().strip()
        
    # Expected: ACCEL must come before TEMP mathematically. 
    # Also verifies the specific separator format required by the ESA problem.
    expected = "2026-04-14T08:00:00Z;NOMINAL;ACCEL-02:1.2|TEMP-01:25.5"
    assert content == expected, "Writer failed to sort sensors alphabetically!"

def test_write_alarms_missing_columns(temp_output_dir, caplog):
    """
    EDGE CASE: If the RulesEngine accidentally returns a DataFrame missing
    the 'rule_id' column, the writer must NOT crash the SLURM job. It should
    catch the KeyError, print an error, and safely return.
    """
    writer = CSVOutputWriter(output_dir=temp_output_dir)
    
    # Missing 'rule_id' and 'priority'
    bad_alarm_data = pl.DataFrame({
        'timestamp': ['2026-04-14T08:00:00Z'],
        'sensor_id': ['TEMP-01'],
        'value': [99.9]
    })
    
    # This should NOT raise an exception
    writer.write_alarms_batch(bad_alarm_data)
    
    # Capture standard output to verify the error was logged gracefully
    assert "OutputWriter missing columns" in caplog.text
    assert not os.path.exists(writer.alarms_path), "Should not write corrupted data to disk"

def test_empty_dataframe_handling(temp_output_dir):
    """EDGE CASE: Passing empty dataframes should be ignored gracefully."""
    writer = CSVOutputWriter(output_dir=temp_output_dir)
    empty_df = pl.DataFrame()
    
    writer.write_valid_batch(empty_df)
    writer.write_alarms_batch(empty_df)
    
    assert not os.path.exists(writer.valid_path)
    assert not os.path.exists(writer.alarms_path)
