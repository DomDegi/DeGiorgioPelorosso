import pytest
from src.state_memory import DictStateMemory

# ==========================================
# FIXTURES
# ==========================================
@pytest.fixture
def memory():
    """Provides a fresh, empty DictStateMemory instance for each test."""
    return DictStateMemory()

# ==========================================
# TESTS FOR STATEFUL RULES (Counts)
# ==========================================
def test_initial_count_is_zero(memory):
    """
    Test that asking for the count of an unknown sensor/rule correctly returns 0 
    instead of raising a KeyError.
    """
    count = memory.get_current_count("R1", "UNKNOWN-SENSOR")
    assert count == 0, "Initial count should default to 0"

def test_set_and_get_consecutive_count(memory):
    """Test standard save and retrieve functionality for counts."""
    memory.set_consecutive_count("R3", "VOLT-MAIN", 4)
    
    count = memory.get_current_count("R3", "VOLT-MAIN")
    assert count == 4, "The retrieved count should match the saved count"

def test_count_namespace_isolation(memory):
    """
    CRITICAL TEST: Ensures that different rules tracking the same sensor 
    do not overwrite each other's memory.
    """
    # Rule 3 tracks VOLT-MAIN for drops below 20V
    memory.set_consecutive_count("R3", "VOLT-MAIN", 5)
    
    # Rule 4 might track VOLT-MAIN for spikes above 30V
    memory.set_consecutive_count("R4", "VOLT-MAIN", 2)
    
    assert memory.get_current_count("R3", "VOLT-MAIN") == 5, "R3 count was incorrectly altered"
    assert memory.get_current_count("R4", "VOLT-MAIN") == 2, "R4 count was incorrectly altered"

def test_count_overwrite_updates_value(memory):
    """Test that a new batch correctly overwrites the streak from the previous batch."""
    # End of Batch 1
    memory.set_consecutive_count("R1", "TEMP-01", 3)
    
    # End of Batch 2 (streak continues)
    memory.set_consecutive_count("R1", "TEMP-01", 8)
    
    assert memory.get_current_count("R1", "TEMP-01") == 8, "Memory failed to overwrite previous count"

# ==========================================
# TESTS FOR STEP DIFFERENCE RULES (Values)
# ==========================================
def test_initial_value_is_none(memory):
    """
    Test that asking for the last value of a completely new sensor returns None.
    This tells the RulesEngine that it's the very first batch.
    """
    val = memory.get_last_value("PRES-01")
    assert val is None, "Initial value must be None for mathematical safety"

def test_set_and_get_last_value(memory):
    """Test standard save and retrieve functionality for float values."""
    memory.set_last_value("PRES-01", 101.5)
    
    val = memory.get_last_value("PRES-01")
    assert val == 101.5, "The retrieved value should match the saved float"

def test_value_overwrite_updates_correctly(memory):
    """Test that values are correctly updated as new batches are processed."""
    # End of Batch 1
    memory.set_last_value("TEMP-MAIN", 45.2)
    
    # End of Batch 2
    memory.set_last_value("TEMP-MAIN", 48.9)
    
    assert memory.get_last_value("TEMP-MAIN") == 48.9, "Memory failed to update to the latest float value"
