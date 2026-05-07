import os
import sys
import pytest
from unittest.mock import patch

# Import your main entry point
from src.main import main

# Define paths to our fixtures
FIXTURES_DIR = os.path.join(os.path.dirname(__file__), 'fixtures')
RULES_PATH = os.path.join(FIXTURES_DIR, 'test_rules.json')
SENSORS_PATH = os.path.join(FIXTURES_DIR, 'test_sensors.yaml')
INPUT_CSV = os.path.join(FIXTURES_DIR, 'test_input.csv')

# Note: We now treat both as text/log files
EXPECTED_VALID = os.path.join(FIXTURES_DIR, 'expected_valid_data.txt')
EXPECTED_ALARMS = os.path.join(FIXTURES_DIR, 'expected_alarms.log')

def test_full_pipeline_execution(tmp_path):
    """
    End-to-End Integration Test via Raw Text Comparison.
    """
    output_dir = str(tmp_path)
    
    test_args = [
        "src/main.py",
        "--batch_size", "5", 
        "--input_path", INPUT_CSV,
        "--output_path", output_dir,
        "--rules_path", RULES_PATH,
        "--sensors_path", SENSORS_PATH
    ]
    
    # Run the application
    with patch.object(sys, 'argv', test_args):
        main()
        
    actual_valid_path = os.path.join(output_dir, 'valid_data.csv')
    actual_alarms_path = os.path.join(output_dir, 'alarms.log')
    
    assert os.path.exists(actual_valid_path), "valid_data.csv was not generated"
    assert os.path.exists(actual_alarms_path), "alarms.log was not generated"
    
    # --- RAW TEXT COMPARISON ---
    
    # 1. Read the actual generated files
    with open(actual_valid_path, 'r') as f:
        actual_valid_lines = [line.strip() for line in f if line.strip()]
        
    with open(actual_alarms_path, 'r') as f:
        actual_alarms_lines = [line.strip() for line in f if line.strip()]

    # 2. If the expected files don't exist yet, this is your first run! 
    # We will automatically save the output as the new Golden Master.
    if not os.path.exists(EXPECTED_VALID) or not os.path.exists(EXPECTED_ALARMS):
        with open(EXPECTED_VALID, 'w') as f:
            f.write("\n".join(actual_valid_lines) + "\n")
        with open(EXPECTED_ALARMS, 'w') as f:
            f.write("\n".join(actual_alarms_lines) + "\n")
        pytest.fail("Golden Master files were missing and have been created. Please review them in the fixtures folder, then run pytest again to pass.")

    # 3. Read the Golden Master files
    with open(EXPECTED_VALID, 'r') as f:
        expected_valid_lines = [line.strip() for line in f if line.strip()]
        
    with open(EXPECTED_ALARMS, 'r') as f:
        expected_alarms_lines = [line.strip() for line in f if line.strip()]

    # 4. Sort lines alphabetically to ignore row order differences between engines
    actual_valid_lines.sort()
    expected_valid_lines.sort()
    actual_alarms_lines.sort()
    expected_alarms_lines.sort()
    
    # 5. Assert equality
    assert actual_valid_lines == expected_valid_lines, "Mismatch in Valid Data output!"
    assert actual_alarms_lines == expected_alarms_lines, "Mismatch in Alarms output!"
