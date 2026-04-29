import os
import tempfile
import yaml
import pytest
from unittest.mock import patch, MagicMock
from src.orchestrator import orchestrator

@pytest.fixture
def mock_environment():
    """Sets up fake configuration files to test the Orchestrator safely."""
    with tempfile.TemporaryDirectory() as tmpdir:
        sensors_path = os.path.join(tmpdir, "sensors.yaml")
        # Fake YAML with exactly 3 sensors
        with open(sensors_path, 'w') as f:
            yaml.dump({'sensors': [{'id': 'S1'}, {'id': 'S2'}, {'id': 'S3'}]}, f)
            
        yield tmpdir, sensors_path

@patch("src.orchestrator.CSVTelemetryReader")
@patch("src.orchestrator.PandasRulesEngine")
@patch("src.orchestrator.CSVOutputWriter")
@patch("src.orchestrator.DictStateMemory")
def test_batch_auto_alignment(MockMemory, MockWriter, MockEngine, MockReader, mock_environment, caplog):
    """
    EDGE CASE: The user asks for a batch_size of 10, but there are 3 sensors.
    10 / 3 = 3.33 (Timestamp split!). The orchestrator MUST auto-adjust 
    the batch to 9 to prevent data corruption.
    """
    tmpdir, sensors_path = mock_environment
    
    # Setup mock reader to return an empty dataframe immediately to end the loop
    mock_reader_instance = MockReader.return_value
    mock_reader_instance.extract_batch.return_value = MagicMock(empty=True)

    # Run orchestrator with dangerous batch size (10)
    orchestrator(
        batch_size=10, 
        input_path="dummy.csv", 
        output_path=tmpdir, 
        rules_path="dummy.json", 
        sensors_path=sensors_path
    )
    
    # Verify the warning was printed
    assert "Requested batch_size (10) splits timestamps" in caplog.text
    assert "Auto-adjusting to safe multiple: 9" in caplog.text
    
    # Verify the Reader was called with the SAFE batch size (9), not 10!
    mock_reader_instance.extract_batch.assert_called_once_with(9)
