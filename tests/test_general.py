"""
End-to-End Integration Testing.

This module constructs a completely isolated, temporary file system utilizing pytest's 
`tmp_path`. It generates mock YAML/JSON configurations and raw CSV data to verify that 
the fully-assembled Composition Root successfully drives data from ingestion to the 
final `alarms.log` and `valid_data.csv` outputs.
"""

import os
import json
import yaml
import pytest
from pathlib import Path

# Import the orchestrator and the concrete implementations
from src.orchestrator import orchestrator
from src.reader import CSVTelemetryReader
from src.rules_engine import PolarsRulesEngine
from src.writer import CSVOutputWriter
from src.state_memory import DictStateMemory

def test_e2e_orchestrator_processing(tmp_path: Path):
    """
    End-to-End test for the orchestrator.
    It creates mock configuration files and a mock CSV input, builds the system 
    components via Dependency Injection, runs the orchestrator, and asserts 
    that alarms and valid data are written correctly.
    """
    
    # ==========================================
    # 1. ARRANGE: Set up the temporary file system
    # ==========================================
    input_dir = tmp_path / "csv_input"
    output_dir = tmp_path / "output"
    config_dir = tmp_path / "config"
    
    input_dir.mkdir()
    output_dir.mkdir()
    config_dir.mkdir()
    
    rules_path = config_dir / "Current_rules_sat_alpha.json"
    sensors_path = config_dir / "Current_sensors_sat_alpha.yaml"
    input_csv_path = input_dir / "mock_input.csv"
    
    # --- Mock Rules (JSON) ---
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
    mock_csv_content = """timestamp,sensor_id,value,priority
2026-05-01T00:00:06Z,TEMP-012,113.59,HIGH
2026-05-01T23:59:59Z,PRES-002,101.3,LOW
"""
    with open(input_csv_path, "w") as f:
        f.write(mock_csv_content)

    # ==========================================
    # 2. ACT: Build Dependencies and Run Orchestrator
    # ==========================================
    
    # Parse total sensors for the orchestrator safety bounds
    with open(sensors_path, 'r') as f:
        total_sensors = len(yaml.safe_load(f)['sensors'])

    # Build the concrete components using our temp paths
    memory = DictStateMemory()
    reader = CSVTelemetryReader(sensors_yaml_path=str(sensors_path), csv_path=str(input_csv_path))
    rules_engine = PolarsRulesEngine(rules_json_path=str(rules_path), memory=memory)
    writer = CSVOutputWriter(output_path=str(output_dir), clean_start=True)

    batch_size = 10 
    
    # Inject components into the orchestrator
    orchestrator(
        reader=reader,
        rules_engine=rules_engine,
        writer=writer,
        batch_size=batch_size, 
        total_sensors=total_sensors
    )

    # ==========================================
    # 3. ASSERT: Verify the outputs
    # ==========================================
    alarms_log_file = output_dir / "alarms.log"
    valid_data_file = output_dir / "valid_data.csv"
    
    assert alarms_log_file.exists(), "alarms.log was not created in the output directory"
    assert valid_data_file.exists(), "valid_data.csv was not created in the output directory"

    with open(alarms_log_file, "r") as f:
        alarms_content = [line.strip() for line in f if line.strip()]
        
    with open(valid_data_file, "r") as f:
        valid_data_content = [line.strip() for line in f if line.strip()]

    expected_alarm = "2026-05-01T00:00:06Z;R002;HIGH;TEMP-012;113.59"
    assert len(alarms_content) == 1, f"Expected exactly 1 alarm, but found {len(alarms_content)}"
    assert alarms_content[0] == expected_alarm, f"Alarm format mismatch. Got: {alarms_content[0]}"

    expected_nominal = "2026-05-01T23:59:59Z;NOMINAL;PRES-002:101.3"
    assert len(valid_data_content) == 1, f"Expected exactly 1 valid data entry, but found {len(valid_data_content)}"
    assert valid_data_content[0] == expected_nominal, f"Valid data format mismatch. Got: {valid_data_content[0]}"