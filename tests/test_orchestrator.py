import pytest
from unittest.mock import MagicMock
from src.orchestrator import orchestrator

def test_batch_auto_alignment(caplog):
    """
    EDGE CASE: The user asks for a batch_size of 10, but there are 3 sensors.
    10 / 3 = 3.33 (Timestamp split!). The orchestrator MUST auto-adjust 
    the batch to 9 to prevent data corruption.
    """
    # 1. Create mock dependencies (Dependency Injection replaces @patch!)
    mock_reader = MagicMock()
    mock_engine = MagicMock()
    mock_writer = MagicMock()
    
    # Setup mock reader to return an empty dataframe immediately to end the loop
    mock_reader.extract_batch.return_value = MagicMock(is_empty=lambda: True, height=0)

    # 2. Run orchestrator with dangerous batch size (10) and 3 total sensors
    orchestrator(
        reader=mock_reader,
        rules_engine=mock_engine,
        writer=mock_writer,
        batch_size=10, 
        total_sensors=3
    )
    
    # 3. Verify the warning was printed
    assert "splits timestamps" in caplog.text
    assert "Auto-adjusting to safe multiple: 9" in caplog.text
    
    # 4. Verify the Reader was called with the SAFE batch size (9), not 10!
    mock_reader.extract_batch.assert_called_once_with(9)


def test_oom_protection_and_alignment(caplog):
    """
    EDGE CASE: The user asks for a massive batch_size of 10,000,000. 
    The orchestrator MUST cap this to MAX_SAFE_BATCH (5,000,000) to prevent RAM crashes, 
    and THEN auto-align it to the nearest multiple of sensors.
    """
    mock_reader = MagicMock()
    mock_engine = MagicMock()
    mock_writer = MagicMock()
    
    mock_reader.extract_batch.return_value = MagicMock(is_empty=lambda: True, height=0)

    # Run orchestrator with 10M rows and 3 total sensors
    orchestrator(
        reader=mock_reader,
        rules_engine=mock_engine,
        writer=mock_writer,
        batch_size=10_000_000, 
        total_sensors=3
    )
    
    # Verify the OOM warning triggered
    assert "exceeds RAM safety limits" in caplog.text
    
    # Calculate the expected safe alignment: 
    # Cap = 5,000,000
    # Safe Multiple = (5,000,000 // 3) * 3 = 4,999,998
    mock_reader.extract_batch.assert_called_once_with(4_999_998)