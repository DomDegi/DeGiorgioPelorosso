"""
Unit tests for the Core Orchestrator.

These tests verify the structural safety mechanisms of the Orchestrator. By utilizing
Mock objects and Dependency Injection, we bypass actual file I/O to strictly evaluate
the mathematical constraints: Out-Of-Memory (OOM) hard-caps and batch size auto-alignment
to prevent timestamp corruption.
"""

from unittest.mock import MagicMock

import pytest
from src.orchestrator import orchestrator


def test_batch_auto_alignment(caplog: pytest.LogCaptureFixture):
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
        total_sensors=3,
    )

    # 3. Verify the warning was printed
    assert "Auto-adjusting batch_size from 10 to safe multiple: 9" in caplog.text

    # 4. Verify the Reader was called with the SAFE batch size (9), not 10!
    mock_reader.extract_batch.assert_called_once_with(9)


def test_oom_protection_and_alignment(caplog: pytest.LogCaptureFixture):
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
        total_sensors=3,
    )

    # Verify the OOM warning triggered
    assert "exceeds RAM limits" in caplog.text

    # Calculate the expected safe alignment:
    # Cap = 5,000,000
    # Safe Multiple = (5,000,000 // 3) * 3 = 4,999,998
    mock_reader.extract_batch.assert_called_once_with(4_999_998)


def test_orchestrator_raises_value_error():
    """
    EDGE CASE: The user asks for an invalid batch size (e.g., 0 or negative).
    The orchestrator MUST immediately raise a ValueError to prevent a crash.
    """

    mock_reader = MagicMock()
    mock_engine = MagicMock()
    mock_writer = MagicMock()

    # We use pytest.raises to assert that the specific exception is thrown
    with pytest.raises(ValueError, match="batch_size must be strictly positive"):
        orchestrator(
            reader=mock_reader,
            rules_engine=mock_engine,
            writer=mock_writer,
            batch_size=0,  # Invalid batch size
            total_sensors=3,
        )
