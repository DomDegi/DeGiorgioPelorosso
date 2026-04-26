import pandas as pd
import operator
import json
from typing import Tuple
from .interfaces import IRulesEngine, IStateMemory

class PandasRulesEngine(IRulesEngine):
    
    # Class-level dictionary for lightning-fast operator lookup.
    # Maps the JSON string operators to compiled Python math operators.
    OPERATORS = {
        ">": operator.gt,
        "<": operator.lt,
        ">=": operator.ge,
        "<=": operator.le,
        "==": operator.eq,
        "!=": operator.ne
    }

    def __init__(self, rules_json_path: str, memory: IStateMemory):
        self.rules = self._load_rules(rules_json_path)
        self.memory = memory
        
        # Order by priority (High through Low)
        self._sort_rules_by_priority()

    def _load_rules(self, path: str) -> list:
        with open(path, 'r') as f:
            return json.load(f)
            
    def _evaluate_simple_rule(self, batch: pd.DataFrame, rule: dict) -> pd.Series:
        """
        Evaluates a simple absolute threshold rule.
        
        Args:
            batch: The clean telemetry DataFrame.
            rule: A single rule dictionary from the JSON.
            
        Returns:
            pd.Series: A boolean mask. True means the row triggered an alarm.
        """
        # 1. Create a mask to isolate ONLY the rows belonging to the target sensor.
        # Example: [True, False, False, True] for TEMP-01
        sensor_mask = batch['sensor_id'] == rule['sensor_id']
        
        # 2. Fetch the correct mathematical operation safely
        op_func = self.OPERATORS.get(rule['operator'])
        if not op_func:
            raise ValueError(f"CRITICAL: Unknown operator '{rule['operator']}' in rule {rule['rule_id']}")
            
        # 3. Apply the mathematical operator to the ENTIRE 'value' column at once.
        # Example: If operator is '>', this translates to batch['value'] > 50.0
        value_mask = op_func(batch['value'], rule['value'])
        
        # 4. Logical AND: An alarm triggers ONLY IF it's the right sensor AND the value breached the threshold.
        alarm_mask = sensor_mask & value_mask
        
        return alarm_mask

    def _evaluate_step_rule(self, batch: pd.DataFrame, rule: dict) -> pd.Series:
        pass

    def _evaluate_stateful_rule(self, batch: pd.DataFrame, rule: dict) -> pd.Series:
        pass

    def _evaluate_correlation_rule(self, batch: pd.DataFrame, rule: dict, previous_results: dict) -> pd.Series:
        pass

    def evaluate_rules(self, telemetry_batch: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        This is the main method: it executes all the rule validations and returns the divided batch (valid_telemetry, alarm_telemetry).
        """
        pass
