import polars as pl
import json
import logging
from typing import Tuple
from src.interfaces import IRulesEngine, IStateMemory

logger = logging.getLogger(__name__)

class PolarsRulesEngine(IRulesEngine):
    def __init__(self, rules_path: str):
        with open(rules_path, 'r') as f:
            self.rules = json.load(f)
            
        # 1. Pre-categorize rules 
        # Separating them prevents us from checking the 'type' string on every single row.
        self.simple_rules = [r for r in self.rules if r['type'] == 'simple']
        self.step_rules = [r for r in self.rules if r['type'] == 'step_difference']
        self.stateful_rules = [r for r in self.rules if r['type'] == 'stateful']
        self.correlation_rules = [r for r in self.rules if r['type'] == 'correlation']

    def evaluate_rules(self, batch: pl.DataFrame, memory: IStateMemory) -> Tuple[pl.DataFrame, pl.DataFrame]:
        if batch.height == 0:
            return batch, pl.DataFrame()

        alarms_list = []
        
        # ==========================================
        # PHASE 1: Vectorized Simple Rules
        # ==========================================
        # These are evaluated across the entire batch instantly using C-level masks.
        for rule in self.simple_rules:
            if rule['operator'] == '>': cond = pl.col('value') > rule['value']
            elif rule['operator'] == '<': cond = pl.col('value') < rule['value']
            elif rule['operator'] == '==': cond = pl.col('value') == rule['value']
                
            triggered = batch.filter((pl.col('sensor_id') == rule['sensor_id']) & cond)
            
            if triggered.height > 0:
                alarm_df = triggered.with_columns(
                    pl.lit(rule['rule_id']).alias('rule_id'),
                    pl.lit(rule['priority']).alias('priority')
                )
                alarms_list.append(alarm_df)

        # ==========================================
        # PHASE 2: Stateful & Step Rules (Sequential)
        # ==========================================
        # Because these rely on cross-batch historical memory, we must iterate.
        # Polars iter_rows() is highly optimized for extracting native Python types.
        state_alarms = []
        for row in batch.iter_rows(named=True):
            
            # Step Rules
            for rule in self.step_rules:
                if row['sensor_id'] == rule['sensor_id']:
                    last_val = memory.get_last_value(rule['sensor_id'])
                    if last_val is not None:
                        diff = abs(row['value'] - last_val)
                        if self._evaluate_condition(diff, rule['operator'], rule['value']):
                            state_alarms.append(self._create_alarm_dict(row, rule))
                    memory.update_last_value(rule['sensor_id'], row['value'])

            # Stateful Rules
            for rule in self.stateful_rules:
                 if row['sensor_id'] == rule['sensor_id']:
                     is_breach = self._evaluate_condition(row['value'], rule['operator'], rule['value'])
                     streak = memory.update_streak(rule['rule_id'], is_breach)
                     if streak >= rule['consecutive_measurements']:
                         state_alarms.append(self._create_alarm_dict(row, rule))
                         
        if state_alarms:
            alarms_list.append(pl.DataFrame(state_alarms))

        # ==========================================
        # PHASE 3: Correlation Rules
        # ==========================================
        if not alarms_list:
            return batch, pl.DataFrame()

        # Combine all alarms found so far into one master table
        all_alarms = pl.concat(alarms_list, how="vertical")
        
        for rule in self.correlation_rules:
            # Group by timestamp to see all rules triggered at that exact second
            grouped = all_alarms.group_by('timestamp').agg(pl.col('rule_id').alias('triggered_rules'))
            
            for row in grouped.iter_rows(named=True):
                triggered_set = set(row['triggered_rules'])
                if rule['logic'] == 'AND' and all(c in triggered_set for c in rule['conditions']):
                    alarms_list.append(pl.DataFrame([{
                        "timestamp": row['timestamp'],
                        "rule_id": rule['rule_id'],
                        "sensor_id": "CORRELATION",
                        "value": None, 
                        "priority": rule['priority']
                    }]))

        # Final Cleanup: Deduplicate and sort
        final_alarms = pl.concat(alarms_list, how="vertical").unique(subset=['timestamp', 'rule_id', 'sensor_id'])
        return batch, final_alarms

    def _evaluate_condition(self, val, operator, threshold):
        if operator == '>': return val > threshold
        if operator == '<': return val < threshold
        if operator == '==': return val == threshold
        return False
        
    def _create_alarm_dict(self, row, rule):
        return {
            "timestamp": row["timestamp"], "rule_id": rule["rule_id"],
            "sensor_id": row["sensor_id"], "value": row["value"],
            "priority": rule["priority"]
        }