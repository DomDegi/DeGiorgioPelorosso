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
    
    with open(valid_path, 'w') as f:
        f.write("OLD CORRUPTED DATA")
        
    writer = CSVOutputWriter(output_path=temp_output_dir, clean_start=True)
    assert not os.path.exists(valid_path), "Writer did not remove old files on clean start"

def test_write_valid_batch_determinism(temp_output_dir):
    """
    EDGE CASE: CI/CD Determinism. The writer MUST sort the sensors alphabetically
    to guarantee the output string is identical regardless of the input row order.
    """
    writer = CSVOutputWriter(output_path=temp_output_dir)
    
    data = pl.DataFrame({
        'timestamp': ['2026-04-14T08:00:00Z', '2026-04-14T08:00:00Z'],
        'sensor_id': ['TEMP-01', 'ACCEL-02'],
        'value': [25.5, 1.2]
    })
    
    writer.write_valid_batch(data)
    
    with open(writer.valid_file_path, 'r') as f:
        content = f.read().strip()
        
    expected = "2026-04-14T08:00:00Z;NOMINAL;ACCEL-02:1.2|TEMP-01:25.5"
    assert content == expected, "Writer failed to sort sensors alphabetically!"

def test_write_alarms_missing_columns(temp_output_dir, caplog):
    """
    EDGE CASE: Catch Missing Columns.
    """
    writer = CSVOutputWriter(output_path=temp_output_dir)
    
    bad_alarm_data = pl.DataFrame({
        'timestamp': ['2026-04-14T08:00:00Z'],
        'sensor_id': ['TEMP-01'],
        'value': [99.9]
    })
    
    writer.write_alarms_batch(bad_alarm_data)
    
    assert "OutputWriter missing columns" in caplog.text
    assert not os.path.exists(writer.alarms_file_path), "Should not write corrupted data to disk"

def test_empty_dataframe_handling(temp_output_dir):
    """EDGE CASE: Passing empty dataframes should be ignored gracefully."""
    writer = CSVOutputWriter(output_path=temp_output_dir)
    empty_df = pl.DataFrame()
    
    writer.write_valid_batch(empty_df)
    writer.write_alarms_batch(empty_df)
    
    assert not os.path.exists(writer.valid_file_path)
    assert not os.path.exists(writer.alarms_file_path)