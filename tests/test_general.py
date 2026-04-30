import os
import json
import pytest
from pathlib import Path
from src.orchestrator import orchestrator

def test_e2e_orchestrator_processing(tmp_path: Path):
    """
    End-to-End test for the orchestrator.
    It creates mock configuration files and a mock CSV input, runs the 
    orchestrator, and asserts that alarms and valid data are written correctly.
    """
    
    # ==========================================
    # 1. ARRANGE: Set up the temporary file system
    # ==========================================
    # tmp_path is a built-in pytest fixture that provides a unique temporary directory
    input_dir = tmp_path / "csv_input"
    output_dir = tmp_path / "output"
    config_dir = tmp_path / "config"
    
    # Create the directories
    input_dir.mkdir()
    output_dir.mkdir()
    config_dir.mkdir()
    
    # Define file paths
    rules_path = config_dir / "Current_rules_sat_alpha.json"
    sensors_path = config_dir / "Current_sensors_sat_alpha.yaml"
    input_csv_path = input_dir / "mock_input.csv"
    
    # --- Mock Rules (JSON) ---
    # Includes the exact rule snippet provided
    mock_rules = [
        {
            "rule_id": "R001",
            "type": "stateful",
            "sensor_id": "FLOW-006",
            "operator": "<",
            "value": 78.48,
            "priority": "MEDIUM",
            "consecutive_measurements": 5
        },
        {
            "rule_id": "R002",
            "type": "simple",
            "sensor_id": "TEMP-012",
            "operator": ">",
            "value": 94.25,
            "priority": "HIGH"
        },
        {
            "rule_id": "R003",
            "type": "step_difference",
            "sensor_id": "HUM-010",
            "operator": "<",
            "value": 46.88,
            "priority": "LOW"
        }
    ]
    with open(rules_path, "w") as f:
        json.dump(mock_rules, f)

    # --- Mock Sensors (YAML) ---
    # Formatted exactly like the real Current_sensors_sat_alpha.yaml
    mock_sensors_yaml = """
sensors:
- id: TEMP-012
  sampling_rate: 1Hz
  unit: Celsius
- id: PRES-002
  sampling_rate: 1Hz
  unit: Bar
spacecraft_id: GEN-2415
"""
    with open(sensors_path, "w") as f:
        f.write(mock_sensors_yaml.strip())

    # --- Mock Input Data (CSV) ---
    # Row 1: Triggers R002 (113.59 > 94.25) -> Goes to alarms.log
    # Row 2: Perfect reading -> Goes to valid_data.csv
    mock_csv_content = """timestamp,sensor_id,value,priority
2026-05-01T00:00:06Z,TEMP-012,113.59,HIGH
2026-05-01T23:59:59Z,PRES-002,101.3,LOW
"""
    with open(input_csv_path, "w") as f:
        f.write(mock_csv_content)

    # ==========================================
    # 2. ACT: Run the Orchestrator
    # ==========================================
    # We call the orchestrator using our isolated temporary paths.
    # Batch size is hardcoded to a small number for testing purposes.
    batch_size = 10 
    
    orchestrator(
        batch_size=batch_size, 
        input_path=str(input_csv_path),
        output_path=str(output_dir), # Pass the folder, not a file, matching main.py logic
        rules_path=str(rules_path),
        sensors_path=str(sensors_path),
        mode="csv"
    )

    # ==========================================
    # 3. ASSERT: Verify the outputs
    # ==========================================
    alarms_log_file = output_dir / "alarms.log"
    valid_data_file = output_dir / "valid_data.csv"
    
    # Check that both files were successfully created
    assert alarms_log_file.exists(), "alarms.log was not created in the output directory"
    assert valid_data_file.exists(), "valid_data.csv was not created in the output directory"

    # Read the output files, ignoring empty lines
    with open(alarms_log_file, "r") as f:
        alarms_content = [line.strip() for line in f if line.strip()]
        
    with open(valid_data_file, "r") as f:
        valid_data_content = [line.strip() for line in f if line.strip()]

    # Validate alarms.log format and content
    # Expected: 2026-05-01T00:00:06Z;R002;HIGH;TEMP-012;113.59
    expected_alarm = "2026-05-01T00:00:06Z;R002;HIGH;TEMP-012;113.59"
    assert len(alarms_content) == 1, f"Expected exactly 1 alarm, but found {len(alarms_content)}"
    assert alarms_content[0] == expected_alarm, f"Alarm format mismatch. Got: {alarms_content[0]}"

    # Validate valid_data.csv format and content
    # Expected: 2026-05-01T23:59:59Z;NOMINAL;PRES-002:101.3
    expected_nominal = "2026-05-01T23:59:59Z;NOMINAL;PRES-002:101.3"
    assert len(valid_data_content) == 1, f"Expected exactly 1 valid data entry, but found {len(valid_data_content)}"
    assert valid_data_content[0] == expected_nominal, f"Valid data format mismatch. Got: {valid_data_content[0]}"
