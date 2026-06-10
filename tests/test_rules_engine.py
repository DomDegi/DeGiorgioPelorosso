"""
Unit tests for the Polars Rules Engine.

Verifies the mathematical evaluation of the 4 core rule types:
1. **Simple**: Absolute threshold triggers.
2. **Step Difference**: Relative variations requiring memory of previous batches.
3. **Stateful**: Consecutive streak tracking and resetting.
4. **Correlation**: Complex boolean intersections (AND/OR logic).
"""

import pytest
import polars as pl
from unittest.mock import patch

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
        {"rule_id": "R4", "type": "correlation", "logic": "AND", "conditions": ["R1", "R2"], "priority": "HIGH"},
        {"rule_id": "R5", "type": "correlation", "logic": "OR", "conditions": ["R1", "R3"], "priority": "MEDIUM"} 
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
        'value': [40.0, 55.0, 60.0] 
    })
    
    valid, alarms = engine.evaluate_rules(batch)
    
    assert alarms.height == 1
    assert alarms['timestamp'][0] == 'T2'
    assert alarms['rule_id'][0] == 'R1'

def test_evaluate_step_rule_with_memory_bridge(engine):
    """Test that relative variation works AND retrieves previous batch data."""
    engine.rules = [r for r in engine.rules if r['rule_id'] == 'R2']

    # Pretend the previous batch ended with PRES-01 at 100.0
    engine.memory.set_last_value('PRES-01', 100.0)

    batch = pl.DataFrame({
        'timestamp': ['T1', 'T2'],
        'sensor_id': ['PRES-01', 'PRES-01'],
        'value': [97.0, 96.0] 
        # Row 0: 97.0 - 100.0 (from memory) = -3.0 (ALARM!)
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
        # Row 3 triggers the alarm (Streak reaches 3)
    })
    
    valid, alarms = engine.evaluate_rules(batch)
    
    assert alarms.height == 1
    assert alarms['timestamp'][0] == 'T4'

# ==========================================
# TESTS FOR CORRELATION LOGIC EDGE CASES
# ==========================================

def test_correlation_rule_logic_and(engine):
    """
    EDGE CASE: A correlation rule with 'AND' logic should only trigger 
    if ALL conditions are met AT THE EXACT SAME TIMESTAMP.
    """
    engine.rules = [r for r in engine.rules if r['rule_id'] in ['R1', 'R2', 'R4']]
    
    # Bridge memory so R2 actually evaluates successfully on T1
    engine.memory.set_last_value('PRES-01', 100.0)

    telemetry = pl.DataFrame({
        'timestamp': ['T1', 'T1', 'T2', 'T2'],
        'sensor_id': ['TEMP-01', 'PRES-01', 'TEMP-01', 'PRES-01'],
        'value': [55.0, 97.0, 45.0, 93.0] 
        # T1: TEMP > 50 (T), PRES drops > 2 (T). Result: AND Triggers
        # T2: TEMP > 50 (F), PRES drops > 2 (T). Result: No AND Trigger
    })
    
    valid_df, alarm_df = engine.evaluate_rules(telemetry)
    
    # We expect 3 total alarms at T1 (R1 base, R2 base, and R4 correlation)
    # We expect 1 alarm at T2 (R2 base only)
    assert alarm_df.height == 4
    
    # Verify the correlation alarm was specifically generated
    correlation_alarms = alarm_df.filter(pl.col('rule_id') == 'R4')
    assert correlation_alarms.height == 1
    assert correlation_alarms['timestamp'][0] == 'T1'

def test_correlation_rule_logic_or(engine):
    """
    EDGE CASE: OR logic should trigger if AT LEAST ONE condition is met in the timestamp.
    """
    engine.rules = [r for r in engine.rules if r['rule_id'] in ['R1', 'R3', 'R5']]
    
    # Inject a 2-streak into memory so R3 triggers on its very first reading
    engine.memory.set_consecutive_count('R3', 'VOLT-MAIN', 2)

    telemetry = pl.DataFrame({
        'timestamp': ['T1', 'T1'],
        'sensor_id': ['TEMP-01', 'VOLT-MAIN'],
        'value': [40.0, 15.0] 
        # T1: TEMP > 50 (False), VOLT < 20 (True, hits streak 3). Result: OR Triggers
    })
    
    valid_df, alarm_df = engine.evaluate_rules(telemetry)
    
    # We expect 2 alarms total: R3 (base) and R5 (correlation)
    assert alarm_df.height == 2
    assert 'R5' in alarm_df['rule_id'].to_list()

# ==========================================
# TESTS FOR ORCHESTRATOR / PIPELINE EDGE CASES
# ==========================================

def test_missing_sensor_guard_clause(engine):
    """
    EDGE CASE: The rules.json asks to monitor a sensor that is entirely missing 
    from the current batch. The system must not crash.
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

def test_priority_sorting(engine):
    """
    EDGE CASE: Output alarms must be strictly sorted by priority (HIGH -> MEDIUM -> LOW).
    """
    batch = pl.DataFrame({
        'timestamp': ['T1', 'T1', 'T1'],
        'sensor_id': ['TEMP-01', 'PRES-01', 'VOLT-MAIN'],
        'value': [60.0, 95.0, 10.0] 
    })
    
    # Manually map rule conditions to ensure they all fire simultaneously
    engine.rules = [
        {"rule_id": "R1", "type": "simple", "sensor_id": "TEMP-01", "operator": ">", "value": 50.0, "priority": "LOW"},
        {"rule_id": "R2", "type": "simple", "sensor_id": "PRES-01", "operator": "<", "value": 100.0, "priority": "HIGH"},
        {"rule_id": "R3", "type": "simple", "sensor_id": "VOLT-MAIN", "operator": "<", "value": 20.0, "priority": "MEDIUM"},
    ]
    
    valid_df, alarm_df = engine.evaluate_rules(batch)
    
    assert alarm_df.height == 3
    # Validate exact sorting order (HIGH -> MEDIUM -> LOW)
    assert alarm_df['priority'][0] == 'HIGH'
    assert alarm_df['priority'][1] == 'MEDIUM'
    assert alarm_df['priority'][2] == 'LOW'


def test_invalid_operator_guard(engine):
    """EDGE CASE: An invalid operator in rules.json should not crash the engine."""
    engine.rules = [{
        "rule_id": "R_BAD", "type": "simple", "sensor_id": "TEMP-01", 
        "operator": "MAGIC_OPERATOR", "value": 50.0, "priority": "HIGH"
    }]
    batch = pl.DataFrame({'timestamp': ['T1'], 'sensor_id': ['TEMP-01'], 'value': [40.0]})
    
    # It should either return 0 alarms safely or raise a specific known Exception
    valid, alarms = engine.evaluate_rules(batch)
    assert alarms.height == 0
