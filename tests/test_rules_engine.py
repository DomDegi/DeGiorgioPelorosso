import pytest
import polars as pl
from unittest.mock import patch
from polars.testing import assert_frame_equal

from src.rules_engine import PolarsRulesEngine
from src.state_memory import DictStateMemory

# ==========================================
# FIXTURES
# ==========================================
@pytest.fixture
def dummy_rules():
    """Provides a mock list of rules mimicking the content of rules.json."""
    return [
        {"rule_id": "R1", "type": "simple", "sensor_id": "TEMP-01", "operator": ">", "value": 50.0, "priority": "MEDIUM"},
        {"rule_id": "R2", "type": "step_difference", "sensor_id": "PRES-01", "operator": "<", "value": -2.0, "priority": "LOW"},
        {"rule_id": "R3", "type": "stateful", "sensor_id": "VOLT-MAIN", "operator": "<", "value": 20.0, "consecutive_measurements": 3, "priority": "HIGH"},
        {"rule_id": "R4", "type": "correlation", "logic": "AND", "conditions": ["R1", "R2"], "priority": "HIGH"}
    ]

@pytest.fixture
def engine(dummy_rules):
    """
    Creates an instance of PolarsRulesEngine without reading a real JSON file.
    It patches '_load_rules' to return our dummy_rules instead.
    """
    memory = DictStateMemory()
    with patch.object(PolarsRulesEngine, '_load_rules', return_value=dummy_rules):
        return PolarsRulesEngine(rules_json_path="fake_path.json", memory=memory)

# ==========================================
# TESTS FOR INDIVIDUAL RULES
# ==========================================

def test_evaluate_simple_rule(engine):
    """Test that a simple absolute threshold rule triggers correctly.""" 
    engine.rules = [r for r in engine.rules if r['rule_id'] == 'R1']

    batch = pl.DataFrame({
        'timestamp': ['T1', 'T2', 'T3'],
        'sensor_id': ['TEMP-01', 'TEMP-01', 'OTHER'],
        'value': [40.0, 55.0, 60.0] # 55.0 is the only violation for TEMP-01
    })
    
    valid, alarms = engine.evaluate_rules(batch)
    
    assert alarms.height == 1
    assert alarms['timestamp'][0] == 'T2'
    assert alarms['rule_id'][0] == 'R1'

def test_evaluate_step_rule_with_memory_bridge(engine):
    """Test that relative variation works AND retrieves previous batch data."""
    engine.rules = [r for r in engine.rules if r['rule_id'] == 'R2']

    # Let's pretend the previous batch ended with PRES-01 at 100.0
    engine.memory.set_last_value('PRES-01', 100.0)

    batch = pl.DataFrame({
        'timestamp': ['T1', 'T2'],
        'sensor_id': ['PRES-01', 'PRES-01'],
        'value': [97.0, 96.0] 
        # Row 0: 97.0 - 100.0 (from memory) = -3.0 (ALARM!)
        # Row 1: 96.0 - 97.0 = -1.0 (SAFE)
    })
    
    valid, alarms = engine.evaluate_rules(batch)
    
    assert alarms.height == 1
    assert alarms['timestamp'][0] == 'T1'
    assert engine.memory.get_last_value('PRES-01') == 96.0

def test_evaluate_stateful_rule_exact_trigger(engine):
    """Test that an anomaly only triggers upon reaching N consecutive failures.""" 
    engine.rules = [r for r in engine.rules if r['rule_id'] == 'R3']

    batch = pl.DataFrame({
        'timestamp': ['T1', 'T2', 'T3', 'T4', 'T5'],
        'sensor_id': ['VOLT-MAIN', 'VOLT-MAIN', 'VOLT-MAIN', 'VOLT-MAIN', 'VOLT-MAIN'],
        'value': [25.0, 19.0, 18.0, 17.0, 22.0]
        # Row 0: Safe (Streak 0)
        # Row 1: Fail (Streak 1)
        # Row 2: Fail (Streak 2)
        # Row 3: Fail (Streak 3) -> ALARM TRIGGERS HERE!
        # Row 4: Safe (Streak 0) -> Reset
    })
    
    valid, alarms = engine.evaluate_rules(batch)
    
    assert alarms.height == 1
    assert alarms['timestamp'][0] == 'T4'

# ==========================================
# TESTS FOR THE ORCHESTRATOR EDGE CASES
# ==========================================

def test_orchestrator_separates_valid_and_alarms(engine):
    """
    Integration test: ensure the main evaluate_rules method correctly 
    routes data into the valid and alarms DataFrames.
    """
    batch = pl.DataFrame({
        'timestamp': ['2026-04-24T10:00Z', '2026-04-24T10:01Z'],
        'sensor_id': ['TEMP-01', 'PRES-01'],
        'value': [60.0, 100.0], 
        'priority': ['HIGH', 'LOW']
    })
    
    valid_df, alarms_df = engine.evaluate_rules(batch)
    
    assert valid_df.height == 1
    assert valid_df['sensor_id'][0] == 'PRES-01'
    
    assert alarms_df.height == 1
    assert alarms_df['sensor_id'][0] == 'TEMP-01'
    assert alarms_df['rule_id'][0] == 'R1'

def test_stateful_rule_streak_reset(engine):
    """
    EDGE CASE: A stateful rule requires 3 consecutive errors. 
    The rule MUST reset on the 'Valid' and NOT trigger an alarm on the final Error.
    """
    telemetry = pl.DataFrame({
        'timestamp': ['T1', 'T2', 'T3', 'T4'],
        'sensor_id': ['VOLT-01', 'VOLT-01', 'VOLT-01', 'VOLT-01'],
        'value': [10.0, 10.0, 25.0, 10.0]
    })
    
    engine.rules = [{
        "rule_id": "R1", "type": "stateful", "sensor_id": "VOLT-01", 
        "operator": "<", "value": 20.0, "consecutive_measurements": 3, "priority": "HIGH"
    }]
    
    valid_df, alarm_df = engine.evaluate_rules(telemetry)
    assert alarm_df.height == 0, "Stateful rule failed to reset streak upon receiving valid data!"

def test_missing_sensor_guard_clause(engine):
    """
    EDGE CASE: The rules.json asks to monitor 'TEMP-05', but the current
    batch doesn't contain any readings for 'TEMP-05'.
    """
    telemetry = pl.DataFrame({
        'timestamp': ['T1'],
        'sensor_id': ['PRES-02'],
        'value': [101.3]
    })
    
    engine.rules = [{
        "rule_id": "R1", "type": "simple", "sensor_id": "TEMP-05", 
        "operator": ">", "value": 50.0, "priority": "HIGH"
    }]
    
    valid_df, alarm_df = engine.evaluate_rules(telemetry)
    
    assert alarm_df.height == 0, "Missing sensor should not generate alarms"
    assert valid_df.height == 1, "Valid data should remain intact"