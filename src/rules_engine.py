import logging
import pandas as pd
import operator
import json
from typing import Tuple
from src.interfaces import IRulesEngine, IStateMemory

logger = logging.getLogger(__name__)

class PandasRulesEngine(IRulesEngine):
    """
    Concrete implementation of the Rules Engine using Pandas vectorized operations.
    Evaluates telemetry batches against JSON-defined constraints (Simple, Step, Stateful, Correlation).
    """
    
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
            raw_rules = json.load(f)
            
        valid_priorities = {"LOW", "MEDIUM", "HIGH"}
        sanitized_rules = []
        
        for rule in raw_rules:
            # 1. Extract priority. If missing, default to LOW.
            priority = rule.get('priority', 'LOW').upper()
            
            # 2. Strict Schema Enforcement
            if priority not in valid_priorities:
                logger.error(f"Rule {rule.get('rule_id')} rejected: Invalid priority '{priority}'. Must be LOW, MEDIUM, or HIGH.")
                continue  # Skip this rule entirely
                
            # 3. Normalize the rule dictionary
            rule['priority'] = priority
            sanitized_rules.append(rule)
            
        return sanitized_rules

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
            logger.error(f"Failed to parse rule {rule['rule_id']}: Unknown operator '{rule['operator']}'. Rule skipped.")
            return pd.Series(False, index=batch.index)
            
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

        # 2. Calculate consecutive streaks
        #   1. '~condition_met' creates boundaries (True becomes False).
        #   2. '.cumsum()' creates unique group IDs for each contiguous block of violations.
        #   3. We group by these IDs and cumulatively sum the True values to get the streak length.    
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
        full_mask.loc[alarm_mask_sensor.index] = alarm_mask_sensor
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
        
        # --- PHASE 1: Base Rules (Simple, Step Difference, Stateful) ---
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

        # --- PHASE 2: Correlation Rules  ---
        correlation_rules = [r for r in self.rules if r['type'] == 'correlation']
        
        # Helper: Map rule_id to its target sensor_id
        rule_to_sensor = {r['rule_id']: r.get('sensor_id') for r in self.rules}

        for rule in correlation_rules:
            cond_a, cond_b = rule['conditions'][0], rule['conditions'][1]
            
            # Get the boolean masks for the parent rules
            mask_a = rule_masks.get(cond_a, pd.Series(False, index=telemetry_batch.index))
            mask_b = rule_masks.get(cond_b, pd.Series(False, index=telemetry_batch.index))
            
            # Extract the unique TIMESTAMPS where the parent rules triggered
            ts_a = set(telemetry_batch[mask_a]['timestamp'])
            ts_b = set(telemetry_batch[mask_b]['timestamp'])
            
            # Evaluate logic at the timestamp level
            if rule['logic'] == 'AND':
                target_ts = ts_a & ts_b
            elif rule['logic'] == 'OR':
                target_ts = ts_a | ts_b
            else:
                target_ts = set()
            
            # Update combined rule_masks so valid_data.csv knows to drop these timestamps
            corr_mask = telemetry_batch['timestamp'].isin(target_ts)
            rule_masks[rule['rule_id']] = corr_mask
            
            if target_ts:
                # Format: "S1,S3"
                parent_sensors = [rule_to_sensor.get(cond_a, "UNKNOWN"), rule_to_sensor.get(cond_b, "UNKNOWN")]
                sensor_str = ",".join(parent_sensors)
                
                # Synthesize the correlation alarm row
                corr_alarms = []
                for ts in sorted(list(target_ts)):
                    ts_data = telemetry_batch[telemetry_batch['timestamp'] == ts]
                    
                    # Extract the exact values for S1 and S3 at this timestamp
                    vals = []
                    for s in parent_sensors:
                        val_series = ts_data[ts_data['sensor_id'] == s]['value']
                        vals.append(str(val_series.iloc[0]) if not val_series.empty else "NaN")
                        
                    corr_alarms.append({
                        'timestamp': ts,
                        'rule_id': rule['rule_id'],
                        'priority': rule.get('priority', 'HIGH'),
                        'sensor_id': sensor_str,
                        'value': ",".join(vals)
                    })
                    
                alarms_list.append(pd.DataFrame(corr_alarms))

        # --- PHASE 3: Separate Valid vs Alarms ---
        
        # If no rules were loaded or parsed, everything is valid
        if not rule_masks:
            return telemetry_batch, pd.DataFrame(columns=['timestamp', 'rule_id', 'priority', 'sensor_id', 'value'])

        # 1. FIND INFECTED TIMESTAMPS
        # Combine all rule masks to find any row that triggered an alarm
        combined_mask = pd.concat(rule_masks.values(), axis=1).any(axis=1)
        infected_rows = telemetry_batch[combined_mask]
        
        # Extract the unique timestamps that contain at least one anomaly
        anomalous_timestamps = infected_rows['timestamp'].unique()

        # 2. CREATE VALID DATA
        valid_telemetry = telemetry_batch[~telemetry_batch['timestamp'].isin(anomalous_timestamps)].copy()

        # 3. CREATE ALARMS DATA
        # We use the pre-compiled alarms_list because it already contains 
        # the injected 'rule_id' and 'priority' metadata required by the Writer.
        if alarms_list:
            alarm_telemetry = pd.concat(alarms_list, ignore_index=True)
            alarm_telemetry = alarm_telemetry[['timestamp', 'rule_id', 'priority', 'sensor_id', 'value']]
            
            # STRICT SORTING: Chronological -> Priority (Desc) -> Rule ID (Asc) -> Sensor ID (Asc)
            prio_map = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
            alarm_telemetry['sort_key'] = alarm_telemetry['priority'].map(prio_map).fillna(1)
            alarm_telemetry = alarm_telemetry.sort_values(
                by=['timestamp', 'sort_key', 'rule_id', 'sensor_id'], 
                ascending=[True, False, True, True]  # True=Ascending, False=Descending
            ).drop(columns=['sort_key'])
            
        else:
            # Return an empty shell if no alarms were found in this batch
            alarm_telemetry = pd.DataFrame(columns=['timestamp', 'rule_id', 'priority', 'sensor_id', 'value'])

        return valid_telemetry, alarm_telemetry





import numpy as np

class NumpyRulesEngine(IRulesEngine):
    """
    High-Performance Rules Engine utilizing raw NumPy C-arrays for 
    vectorized mathematical evaluations, bypassing Pandas iteration overhead.
    """
    
    OPERATORS = {
        ">": operator.gt,
        "<": operator.lt,
        ">=": operator.ge,
        "<=": operator.le,
        "==": operator.eq,
        "!=": operator.ne
    }

    def __init__(self, rules_json_path: str, memory: IStateMemory):
        with open(rules_json_path, 'r') as f:
            self.rules = json.load(f)
        self.memory = memory
        
        # Sort by priority
        priority_map = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
        self.rules.sort(
            key=lambda r: priority_map.get(r.get('priority', 'LOW').upper(), 1), 
            reverse=True
        )
        logger.info(f"NumpyRulesEngine initialized with {len(self.rules)} rules.")

    def _evaluate_simple_rule(self, raw_values: np.ndarray, sensor_mask: np.ndarray, rule: dict, total_rows: int) -> np.ndarray:
        op_func = self.OPERATORS[rule['operator']]
        
        full_mask = np.zeros(total_rows, dtype=bool)
        # Evaluate only where the sensor matches
        full_mask[sensor_mask] = op_func(raw_values[sensor_mask], rule['value'])
        return full_mask

    def _evaluate_step_rule(self, raw_values: np.ndarray, sensor_mask: np.ndarray, rule: dict, total_rows: int) -> np.ndarray:
        sensor_vals = raw_values[sensor_mask]
        full_mask = np.zeros(total_rows, dtype=bool)
        
        if len(sensor_vals) == 0:
            return full_mask

        diffs = np.zeros(len(sensor_vals), dtype=float)
        diffs[1:] = np.diff(sensor_vals)

        # Bridge with State Memory
        last_known = self.memory.get_last_value(rule['sensor_id'])
        if last_known is not None:
            diffs[0] = sensor_vals[0] - last_known
        else:
            diffs[0] = 0.0

        self.memory.set_last_value(rule['sensor_id'], sensor_vals[-1])
        
        op_func = self.OPERATORS[rule['operator']]
        full_mask[sensor_mask] = op_func(diffs, rule['value'])
        return full_mask

    def _evaluate_stateful_rule(self, raw_values: np.ndarray, sensor_mask: np.ndarray, rule: dict, total_rows: int) -> np.ndarray:
        sensor_vals = raw_values[sensor_mask]
        full_mask = np.zeros(total_rows, dtype=bool)
        
        if len(sensor_vals) == 0:
            return full_mask

        op_func = self.OPERATORS[rule['operator']]
        condition_met = op_func(sensor_vals, rule['value'])
        
        # Fast NumPy iteration for streaks
        streaks = np.zeros(len(sensor_vals), dtype=int)
        current_streak = self.memory.get_current_count(rule['rule_id'], rule['sensor_id'])

        for i in range(len(condition_met)):
            if condition_met[i]:
                current_streak += 1
                streaks[i] = current_streak
            else:
                current_streak = 0
                streaks[i] = 0

        self.memory.set_consecutive_count(rule['rule_id'], rule['sensor_id'], current_streak)
        
        full_mask[sensor_mask] = (streaks >= rule['consecutive_measurements'])
        return full_mask

    def evaluate_rules(self, telemetry_batch: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
        if telemetry_batch.empty or not self.rules:
            return telemetry_batch, pd.DataFrame(columns=['timestamp', 'rule_id', 'priority', 'sensor_id', 'value'])

        # 1. Extract to C-arrays
        total_rows = len(telemetry_batch)
        raw_values = telemetry_batch['value'].to_numpy()
        sensor_ids = telemetry_batch['sensor_id'].to_numpy()
        
        rule_masks = {}
        alarms_list = []

        # 2. Evaluate Base Rules
        for rule in [r for r in self.rules if r['type'] != 'correlation']:
            sensor_mask = (sensor_ids == rule['sensor_id'])
            
            if rule['type'] == 'simple':
                mask = self._evaluate_simple_rule(raw_values, sensor_mask, rule, total_rows)
            elif rule['type'] == 'step_difference':
                mask = self._evaluate_step_rule(raw_values, sensor_mask, rule, total_rows)
            elif rule['type'] == 'stateful':
                mask = self._evaluate_stateful_rule(raw_values, sensor_mask, rule, total_rows)
                
            rule_masks[rule['rule_id']] = mask

            # Extract failed rows for logging
            failed_indices = np.where(mask)[0]
            if len(failed_indices) > 0:
                failed_df = telemetry_batch.iloc[failed_indices].copy()
                failed_df['rule_id'] = rule['rule_id']
                failed_df['priority'] = rule.get('priority', 'LOW')
                alarms_list.append(failed_df)

        # 3. Evaluate Correlation Rules
        for rule in [r for r in self.rules if r['type'] == 'correlation']:
            mask_a = rule_masks[rule['conditions'][0]]
            mask_b = rule_masks[rule['conditions'][1]]
            
            mask = (mask_a & mask_b) if rule['logic'] == 'AND' else (mask_a | mask_b)
            rule_masks[rule['rule_id']] = mask
            
            failed_indices = np.where(mask)[0]
            if len(failed_indices) > 0:
                failed_df = telemetry_batch.iloc[failed_indices].copy()
                failed_df['rule_id'] = rule['rule_id']
                failed_df['priority'] = rule.get('priority', 'HIGH')
                failed_df['sensor_id'] = ",".join(rule['conditions'])
                alarms_list.append(failed_df)

        # 4. Filter and Return
        # Find timestamps that have at least one True in ANY mask
        combined_mask = np.any(list(rule_masks.values()), axis=0)
        anomalous_timestamps = telemetry_batch.iloc[np.where(combined_mask)[0]]['timestamp'].unique()

        valid_telemetry = telemetry_batch[~telemetry_batch['timestamp'].isin(anomalous_timestamps)].copy()

        if alarms_list:
            alarm_telemetry = pd.concat(alarms_list, ignore_index=True)
            alarm_telemetry = alarm_telemetry[['timestamp', 'rule_id', 'priority', 'sensor_id', 'value']]
        else:
            alarm_telemetry = pd.DataFrame(columns=['timestamp', 'rule_id', 'priority', 'sensor_id', 'value'])

        return valid_telemetry, alarm_telemetry
