import pytest
import polars as pl
from pathlib import Path
from src.reader import CSVTelemetryReader

def test_reader_cleans_corrupted_rows(tmp_path: Path):
    csv_file = tmp_path / "test_data.csv"
    csv_file.write_text(
        "timestamp,sensor_id,value,priority\n"
        "2026-04-24T10:00Z,TEMP-01,25.5,HIGH\n"
        "BAD_TIME,TEMP-02,WRONG_TYPE,LOW\n"
    )
    
    yaml_file = tmp_path / "sensors.yaml"
    yaml_file.write_text("sensors: []")
    
    reader = CSVTelemetryReader(csv_path=str(csv_file), sensors_yaml_path=str(yaml_file))

    clean_batch = reader.extract_batch(batch_size=10)
    
    assert clean_batch.height == 1
    assert clean_batch["sensor_id"][0] == "TEMP-01"