import pytest
import polars as pl
from unittest.mock import patch, mock_open

from src.rules_engine import PolarsRulesEngine
from src.state_memory import DictStateMemory

# ==========================================
# FIXTURES
# ==========================================
@pytest.fixture
def dummy_rules():
    """
    Provides a mock list of rules mimicking the content of rules.json.
    Notice R2 was updated to use '>' because the Polars engine uses absolute differences (abs).
    """
    return [
        {"rule_id": "R1", "type": "simple", "sensor_id": "TEMP-01", "operator": ">", "value": 50.0, "priority": "MEDIUM"},
        {"rule_id": "R2", "type": "step_difference", "sensor_id": "PRES-01", "operator": ">", "value": 2.0, "priority": "LOW"},
        {"rule_id": "R3", "type": "stateful", "sensor_id": "VOLT-MAIN", "operator": "<", "value": 20.0, "consecutive_measurements": 3, "priority": "HIGH"},
        {"rule_id": "R4", "type": "correlation", "logic": "AND", "conditions": ["R1", "R2"], "priority": "HIGH"}
    ]

@pytest.fixture
def engine(dummy_rules):
    with patch("builtins.open", mock_open(read_data='[]')):
        engine_inst = PolarsRulesEngine(rules_path="fake_path.json")
        
        # Inject our mock rules
        engine_inst.rules = dummy_rules
        
        # Manually categorize rules as the __init__ would do
        engine_inst.simple_rules = [r for r in dummy_rules if r['type'] == 'simple']
        engine_inst.step_rules = [r for r in dummy_rules if r['type'] == 'step_difference']
        engine_inst.stateful_rules = [r for r in dummy_rules if r['type'] == 'stateful']
        engine_inst.correlation_rules = [r for r in dummy_rules if r['type'] == 'correlation']
        
        return engine_inst

# ==========================================
# TESTS FOR INDIVIDUAL RULES
# ==========================================

def test_evaluate_simple_rule(engine):
    """Test that a simple absolute threshold rule triggers correctly.""" 
    batch = pl.DataFrame({
        'timestamp': ['T1', 'T2', 'T3'],
        'sensor_id': ['TEMP-01', 'TEMP-01', 'OTHER'],
        'value': [40.0, 55.0, 60.0] 
        # 55.0 is the only violation for TEMP-01 (Rule R1: > 50.0)
    })
    
    memory = DictStateMemory()
    _, alarms = engine.evaluate_rules(batch, memory)
    
    assert alarms.height == 1
    assert alarms["timestamp"][0] == "T2"
    assert alarms["rule_id"][0] == "R1"

def test_evaluate_step_rule_with_memory_bridge(engine):
    """Test that relative variation works AND retrieves previous batch data via Memory."""
    memory = DictStateMemory()
    
    # Simulate that the previous batch ended with PRES-01 at 100.0
    memory.set_last_value('PRES-01', 100.0)

    batch = pl.DataFrame({
        'timestamp': ['T1', 'T2'],
        'sensor_id': ['PRES-01', 'PRES-01'],
        'value': [97.0, 96.0] 
        # Row 0: abs(97.0 - 100.0) = 3.0 -> > 2.0 (ALARM!)
        # Row 1: abs(96.0 - 97.0) = 1.0 -> < 2.0 (SAFE)
    })
    
    _, alarms = engine.evaluate_rules(batch, memory)
    
    assert alarms.height == 1
    assert alarms["timestamp"][0] == "T1"
    assert alarms["rule_id"][0] == "R2"
    
    # Check that memory was accurately updated for the NEXT batch
    assert memory.get_last_value('PRES-01') == 96.0

def test_evaluate_stateful_rule_exact_trigger(engine):
    """Test that an anomaly only triggers upon reaching N consecutive failures.""" 
    batch = pl.DataFrame({
        'timestamp': ['T1', 'T2', 'T3', 'T4', 'T5'],
        'sensor_id': ['VOLT-MAIN', 'VOLT-MAIN', 'VOLT-MAIN', 'VOLT-MAIN', 'VOLT-MAIN'],
        'value': [25.0, 19.0, 18.0, 17.0, 22.0]
        # Row 0: 25.0 (Safe, Streak 0)
        # Row 1: 19.0 (Fail, Streak 1)
        # Row 2: 18.0 (Fail, Streak 2)
        # Row 3: 17.0 (Fail, Streak 3) -> ALARM TRIGGERS HERE!
        # Row 4: 22.0 (Safe, Streak 0) -> Reset
    })
    
    memory = DictStateMemory()
    _, alarms = engine.evaluate_rules(batch, memory)
    
    assert alarms.height == 1
    assert alarms["timestamp"][0] == "T4"
    assert alarms["rule_id"][0] == "R3"

# ==========================================
# TESTS FOR THE ORCHESTRATOR / EDGE CASES
# ==========================================

def test_orchestrator_separates_valid_and_alarms(engine):
    """
    Integration test: ensure the main evaluate_rules method processes 
    data and generates the alarms DataFrame correctly.
    """
    batch = pl.DataFrame({
        'timestamp': ['2026-04-24T10:00Z', '2026-04-24T10:01Z'],
        'sensor_id': ['TEMP-01', 'PRES-01'],
        'value': [60.0, 100.0], 
        # TEMP-01 is 60.0 (Violates Simple Rule R1 > 50)
        # PRES-01 is 100.0 (Safe)
        'priority': ['HIGH', 'LOW']
    })
    
    memory = DictStateMemory()
    valid_df, alarms_df = engine.evaluate_rules(batch, memory)
    
    # 1. Valid DF in Polars design is the original batch
    assert valid_df.height == 1
    assert valid_df["sensor_id"][0] == 'PRES-01'
    
    # 2. Alarms DF should only contain TEMP-01
    assert alarms_df.height == 1
    assert alarms_df["sensor_id"][0] == 'TEMP-01'
    assert alarms_df["rule_id"][0] == 'R1'

def test_stateful_rule_streak_reset(engine):
    """
    EDGE CASE: A stateful rule requires 3 consecutive errors. 
    The sequence is: Error -> Error -> Valid -> Error.
    The rule MUST reset on the 'Valid' and NOT trigger an alarm on the final Error.
    """
    telemetry = pl.DataFrame({
        'timestamp': ['T1', 'T2', 'T3', 'T4'],
        'sensor_id': ['VOLT-01', 'VOLT-01', 'VOLT-01', 'VOLT-01'],
        'value': [10.0, 10.0, 25.0, 10.0] # 10.0 is an error (e.g., < 20.0)
    })
    
    # Override engine rules for this specific edge case
    engine.stateful_rules = [{
        "rule_id": "R_ST", "type": "stateful", "sensor_id": "VOLT-01", 
        "operator": "<", "value": 20.0, "consecutive_measurements": 3, "priority": "HIGH"
    }]
    engine.simple_rules = []
    engine.step_rules = []
    
    memory = DictStateMemory()
    _, alarm_df = engine.evaluate_rules(telemetry, memory)
    
    # Because of the reset at T3, the streak never hits 3. Alarms should be empty.
    assert alarm_df.height == 0, "Stateful rule failed to reset streak upon receiving valid data!"

def test_missing_sensor_guard_clause(engine):
    """
    EDGE CASE: The rules engine asks to monitor 'TEMP-05', but the current
    batch doesn't contain any readings for 'TEMP-05'. The engine must 
    bypass the rule securely without throwing a KeyError.
    """
    telemetry = pl.DataFrame({
        'timestamp': ['T1'],
        'sensor_id': ['PRES-02'], # TEMP-05 is completely missing
        'value': [101.3]
    })
    
    engine.simple_rules = [{
        "rule_id": "R1", "type": "simple", "sensor_id": "TEMP-05", 
        "operator": ">", "value": 50.0, "priority": "HIGH"
    }]
    
    memory = DictStateMemory()
    valid_df, alarm_df = engine.evaluate_rules(telemetry, memory)
    
    assert alarm_df.height == 0, "Missing sensor should not generate alarms"
    assert valid_df.height == 1, "Valid data should remain intact"