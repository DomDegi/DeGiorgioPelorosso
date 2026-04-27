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

    def _sort_rules_by_priority(self) -> None:
        """
        Orders the list in a way that the rules with HIGH priority get evaluated first.
        """
        # Map the priority strings to numerical value to allow us to order them easily
        priority_map = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
        
        # Ordering the list self rules. If no priority explicitly stated set to LOW priority.
        self.rules.sort(
            key=lambda rule: priority_map.get(rule.get('priority', 'LOW').upper(), 1), 
            reverse=True
        )
            

    # ==========================================
    # 1. SIMPLE RULE 
    # ==========================================
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

    # ==========================================
    # 2. STEP DIFFERENCE RULE (T_n - T_{n-1})
    # ==========================================
    def _evaluate_step_rule(self, batch: pd.DataFrame, rule: dict) -> pd.Series:
        """
        Evaluates the relative variation between consecutive measurements.
        Vectorized using Pandas .diff()
        """
        sensor_mask = batch['sensor_id'] == rule['sensor_id']
        sensor_data = batch[sensor_mask].copy()
        
        if sensor_data.empty:
            return pd.Series(False, index=batch.index)

        # Calculate the difference between current and previous row
        diffs = sensor_data['value'].diff()
        
        # The first row of this batch has no previous row IN THIS BATCH.
        # We must pull the last known value from the State Memory!
        last_known_value = self.memory.get_last_value(rule['sensor_id'])
        if last_known_value is not None:
            # Manually calculate the diff for the very first row
            diffs.iloc[0] = sensor_data['value'].iloc[0] - last_known_value
            
        # Update the memory with the last value of THIS batch for the next loop
        self.memory.set_last_value(rule['sensor_id'], sensor_data['value'].iloc[-1])

        # Evaluate the math condition (e.g., diffs < -2.0)
        op_func = self.OPERATORS.get(rule['operator'])
        alarm_mask_sensor = op_func(diffs, rule['value'])

        # Map the results back to the full batch index
        full_mask = pd.Series(False, index=batch.index)
        full_mask.loc[alarm_mask_sensor.index] = alarm_mask_sensor
        return full_mask

    # ==========================================
    # 3. STATEFUL RULE (Consecutive Measurements)
    # ==========================================
    def _evaluate_stateful_rule(self, batch: pd.DataFrame, rule: dict) -> pd.Series:
        """
        Tracks consecutive violations using advanced Pandas grouping.
        """
        sensor_mask = batch['sensor_id'] == rule['sensor_id']
        sensor_data = batch[sensor_mask]
        
        if sensor_data.empty:
            return pd.Series(False, index=batch.index)

        # 1. Find which rows break the simple threshold
        op_func = self.OPERATORS.get(rule['operator'])
        condition_met = op_func(sensor_data['value'], rule['value']) 

        # 2. Pandas Magic: Calculate consecutive streaks
        # Group by contiguous blocks of True values
        blocks = (~condition_met).cumsum()
        streak_lengths = condition_met.groupby(blocks).cumsum()

        # --- HPC BATCH BRIDGE ---
        # Add the streak count carried over from the previous batch
        current_streak = self.memory.get_current_count(rule['rule_id'], rule['sensor_id'])
        if current_streak > 0 and condition_met.iloc[0]:
            first_block_id = blocks.iloc[0]
            streak_lengths[blocks == first_block_id] += current_streak

        # Update memory for the next batch
        if condition_met.iloc[-1]:
            self.memory.set_consecutive_count(rule['rule_id'], rule['sensor_id'], int(streak_lengths.iloc[-1]))
        else:
            self.memory.set_consecutive_count(rule['rule_id'], rule['sensor_id'], 0)

        # 3. Trigger alarm ONLY if the streak reaches the required number
        alarm_mask_sensor = streak_lengths >= rule['consecutive_measurements']

        full_mask = pd.Series(False, index=batch.index)
        full_mask.update(alarm_mask_sensor)
        return full_mask

    # ==========================================
    # 4. LOGICAL CORRELATION RULE (AND / OR)
    # ==========================================
    def _evaluate_correlation_rule(self, batch: pd.DataFrame, rule: dict, rule_masks: dict) -> pd.Series:
        """
        Combines the boolean masks of previously evaluated rules.
        """
        # Get the masks for the two rules we are correlating (e.g., R1 and R2)
        mask_a = rule_masks[rule['conditions'][0]]
        mask_b = rule_masks[rule['conditions'][1]]

        # Since the masks have the exact same pandas Index (the timestamp/row id),
        # the bitwise operators automatically align them row-by-row!
        if rule['logic'] == 'AND':
            return mask_a & mask_b
        elif rule['logic'] == 'OR':
            return mask_a | mask_b
        else:
            raise ValueError(f"Unknown logic operator: {rule['logic']}")

    # ==========================================
    # THE ORCHESTRATOR METHOD
    # ==========================================
    def evaluate_rules(self, telemetry_batch: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
        
        rule_masks = {}    # Stores the boolean result mask for each rule
        alarms_list = []   # Stores the rows that need to go to alarms.log
        
        # --- PHASE 1: Base Rules (Simple, Step, Stateful) ---
        base_rules = [r for r in self.rules if r['type'] != 'correlation']
        for rule in base_rules:
            if rule['type'] == 'simple':
                mask = self._evaluate_simple_rule(telemetry_batch, rule)
            elif rule['type'] == 'step_difference':
                mask = self._evaluate_step_rule(telemetry_batch, rule)
            elif rule['type'] == 'stateful':
                mask = self._evaluate_stateful_rule(telemetry_batch, rule)
                
            rule_masks[rule['rule_id']] = mask
            
            # If any rows failed this rule, format them for alarms.log
            failed_rows = telemetry_batch[mask].copy()
            if not failed_rows.empty:
                failed_rows['rule_id'] = rule['rule_id']
                failed_rows['priority'] = rule.get('priority', 'LOW')
                alarms_list.append(failed_rows)

        # --- PHASE 2: Correlation Rules ---
        correlation_rules = [r for r in self.rules if r['type'] == 'correlation']
        for rule in correlation_rules:
            mask = self._evaluate_correlation_rule(telemetry_batch, rule, rule_masks)
            rule_masks[rule['rule_id']] = mask
            
            failed_rows = telemetry_batch[mask].copy()
            if not failed_rows.empty:
                failed_rows['rule_id'] = rule['rule_id']
                failed_rows['priority'] = rule.get('priority', 'HIGH')
                # For correlation, specs say: "list all sensors involved".
                # We overwrite the sensor_id with a comma-separated list of the parent sensors.
                parent_sensors = ",".join([r['sensor_id'] for r in self.rules if r['rule_id'] in rule['conditions']])
                failed_rows['sensor_id'] = parent_sensors
                alarms_list.append(failed_rows)

        # --- PHASE 3: Separate Valid vs Alarms ---
        # A row is valid ONLY IF it triggered ZERO alarms across all masks
        combined_mask = pd.concat(rule_masks.values(), axis=1).any(axis=1)
        valid_telemetry = telemetry_batch[~combined_mask]
        
        # Combine all generated alarms into a single DataFrame
        if alarms_list:
            alarm_telemetry = pd.concat(alarms_list, ignore_index=True)
            # Standardize columns for the Writer: TIMESTAMP;RULE_ID;PRIORITY;VIOLATED_SENSOR(S);CURRENT_VALUE(S)
            alarm_telemetry = alarm_telemetry[['timestamp', 'rule_id', 'priority', 'sensor_id', 'value']]
        else:
            # Return an empty dataframe with the correct columns if no alarms triggered
            alarm_telemetry = pd.DataFrame(columns=['timestamp', 'rule_id', 'priority', 'sensor_id', 'value'])

        return valid_telemetry, alarm_telemetry
