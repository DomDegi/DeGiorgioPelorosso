"""
Business Logic and Rule Evaluation Component.

This module is the mathematical heart of the application. It evaluates clean
telemetry against predefined JSON rules using vectorized Polars operations,
optimizing for High-Performance Computing (HPC) execution speeds.
"""

import polars as pl
import json
import logging
from typing import Tuple
from src.interfaces import IRulesEngine, IStateMemory

logger = logging.getLogger(__name__)


class PolarsRulesEngine(IRulesEngine):
    """
    Concrete implementation of IRulesEngine utilizing Polars expressions.

    Evaluates Simple, Step Difference, Stateful, and Correlation rules. Uses a
    provided State Memory object to track streaks and past values across batch boundaries.
    """

    def __init__(self, rules_json_path: str, memory: IStateMemory):
        """
        Initializes the Rules Engine, parses the rule definitions, and mounts the memory.

        Args:
            rules_json_path (str): Path to the JSON rules configuration file.
            memory (IStateMemory): The memory component instance for tracking state.
        """

        self.rules = self._load_rules(rules_json_path)
        self.memory = memory
        self._sort_rules_by_priority()

    def _load_rules(self, path: str) -> list:
        """
        Private helper to load and sanitize rules from a JSON file.
        Implements pre-flight checks suitable for HPC/Slurm environments.

        Args:
            path (str): Path to the JSON rules file.

        Returns:
            list: A list of sanitized and validated rule dictionaries.
        """

        with open(path, "r") as f:
            raw_rules = json.load(f)

        valid_priorities = {"LOW", "MEDIUM", "HIGH"}
        valid_logics = {"AND", "OR"}
        sanitized = []

        for r in raw_rules:
            priority = r.get("priority", "LOW").upper()
            if priority in valid_priorities:
                r["priority"] = priority

                # Slurm Pre-Flight validation for correlation rules
                if r.get("type") == "correlation":
                    logic = r.get("logic", "").upper()
                    if logic not in valid_logics:
                        logger.error(
                            f"[SLURM PRE-FLIGHT] Rule {r.get('rule_id', 'UNKNOWN')} discarded: "
                            f"unknown logic '{logic}'. Expected 'AND' or 'OR'."
                        )
                        continue  # Skip adding this malformed rule
                    r["logic"] = logic

                sanitized.append(r)

        return sanitized

    def _sort_rules_by_priority(self) -> None:
        """
        Sorts the loaded rules in-place to ensure HIGH priority rules are
        evaluated and logged before LOW priority rules.
        """

        prio_map = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
        self.rules.sort(
            key=lambda r: prio_map.get(r.get("priority", "LOW"), 1), reverse=True
        )

    def _get_op_expr(self, col_name: str, operator: str, value: float) -> pl.Expr:
        """
        Translates string-based mathematical operators into Polars Native Expressions.

        Args:
            col_name (str): The DataFrame column to evaluate.
            operator (str): The mathematical operator (e.g., ">", "==").
            value (float): The threshold value to check against.

        Returns:
            pl.Expr: A lazy-evaluated Polars expression representing the logic.
        """

        if operator == ">":
            return pl.col(col_name) > value
        if operator == "<":
            return pl.col(col_name) < value
        if operator == ">=":
            return pl.col(col_name) >= value
        if operator == "<=":
            return pl.col(col_name) <= value
        if operator == "==":
            return pl.col(col_name) == value
        if operator == "!=":
            return pl.col(col_name) != value
        return pl.lit(False)

    def evaluate_rules(self, batch: pl.DataFrame) -> Tuple[pl.DataFrame, pl.DataFrame]:
        """
        Evaluates a batch of raw telemetry against the project rules.

        Processes the batch in three phases:
        1. Base Rules (Fully Vectorized simple, step, and stateful tracking).
        2. Correlation Rules (Logical combinations of base rule masks supporting n-arguments).
        3. Separation & Sorting (Splits the frame into Nominal and Anomalous data).

        Args:
            batch (pl.DataFrame): The sanitized telemetry batch from the Reader.

        Returns:
            Tuple[pl.DataFrame, pl.DataFrame]: A tuple containing (valid_telemetry, alarm_telemetry).
        """

        if batch.height == 0 or not self.rules:
            return batch, pl.DataFrame(
                schema={
                    "timestamp": pl.Utf8,
                    "rule_id": pl.Utf8,
                    "priority": pl.Utf8,
                    "sensor_id": pl.Utf8,
                    "value": pl.Utf8,
                }
            )

        rule_masks = {}
        alarms_list = []

        # 1. Attach original index FIRST to safely map back isolated sensor frames
        # (This completely solves the bug where S2's alarm was mapped to S1)
        batch_with_idx = batch.with_row_count("orig_idx")

        # --- PHASE 1: Base Rules (Fully Vectorized) ---
        for rule in [r for r in self.rules if r["type"] != "correlation"]:
            sensor_mask = batch_with_idx["sensor_id"] == rule["sensor_id"]
            rule_id = rule["rule_id"]

            if rule["type"] == "simple":
                op_mask = batch_with_idx.select(
                    self._get_op_expr("value", rule["operator"], rule["value"])
                ).to_series()
                final_mask = sensor_mask & op_mask

            elif rule["type"] == "step_difference":
                sensor_df = batch_with_idx.filter(sensor_mask)
                if sensor_df.height > 0:
                    last_val = self.memory.get_last_value(rule["sensor_id"])

                    # diff() is natively null on the first row. We patch only that null cleanly.
                    diff_expr = pl.col("value").diff()
                    if last_val is not None:
                        diff_expr = diff_expr.fill_null(pl.col("value") - last_val)
                    else:
                        diff_expr = diff_expr.fill_null(0.0)

                    sensor_df = sensor_df.with_columns(diff_expr.alias("diff_val"))
                    op_mask_sensor = sensor_df.select(
                        self._get_op_expr("diff_val", rule["operator"], rule["value"])
                    ).to_series()

                    self.memory.set_last_value(
                        rule["sensor_id"], sensor_df["value"][-1]
                    )

                    # Safely map back using the exact original global row indices
                    violating_indices = sensor_df.filter(op_mask_sensor)["orig_idx"]
                    final_mask = batch_with_idx["orig_idx"].is_in(violating_indices)
                else:
                    final_mask = pl.Series(name="mask", values=[False] * batch.height)

            elif rule["type"] == "stateful":
                sensor_df = batch_with_idx.filter(sensor_mask)
                if sensor_df.height > 0:
                    op_mask_sensor = sensor_df.select(
                        self._get_op_expr("value", rule["operator"], rule["value"])
                    ).to_series()

                    # Vectorized streak calculation using Cumulative Sum grouping
                    blocks = (~op_mask_sensor).cast(pl.Int32).cum_sum()
                    sensor_df = sensor_df.with_columns(
                        op_mask_sensor.alias("is_breach"), blocks.alias("block")
                    ).with_columns(
                        pl.col("is_breach")
                        .cast(pl.Int32)
                        .cum_sum()
                        .over("block")
                        .alias("streak")
                    )

                    # HPC Bridge: Carry over memory to the first block
                    current_streak = self.memory.get_current_count(
                        rule["rule_id"], rule["sensor_id"]
                    )
                    if current_streak > 0 and sensor_df["is_breach"][0]:
                        first_block = sensor_df["block"][0]
                        sensor_df = sensor_df.with_columns(
                            pl.when(pl.col("block") == first_block)
                            .then(pl.col("streak") + current_streak)
                            .otherwise(pl.col("streak"))
                            .alias(
                                "streak"
                            )  # Update the streak with memory carry-over for the first block
                        )

                    last_streak = (
                        sensor_df["streak"][-1] if sensor_df["is_breach"][-1] else 0
                    )
                    self.memory.set_consecutive_count(
                        rule["rule_id"], rule["sensor_id"], last_streak
                    )

                    streak_mask = (
                        sensor_df["streak"] >= rule["consecutive_measurements"]
                    )

                    # Safely map back using the exact original global row indices
                    violating_indices = sensor_df.filter(streak_mask)["orig_idx"]
                    final_mask = batch_with_idx["orig_idx"].is_in(violating_indices)
                else:
                    final_mask = pl.Series(name="mask", values=[False] * batch.height)

            rule_masks[rule_id] = final_mask

            # Format alarms for valid extraction
            if final_mask.any():
                failed = (
                    batch.filter(final_mask)
                    .with_columns(
                        [
                            pl.lit(rule_id).alias("rule_id"),
                            pl.lit(rule.get("priority", "LOW")).alias("priority"),
                            pl.col("value").cast(pl.Utf8),
                        ]
                    )
                    .select(["timestamp", "rule_id", "priority", "sensor_id", "value"])
                )
                alarms_list.append(failed)

        # --- PHASE 2: Correlation Rules (N-Arguments Support) ---
        rule_to_sensor = {r["rule_id"]: r.get("sensor_id") for r in self.rules}

        for rule in [r for r in self.rules if r["type"] == "correlation"]:
            conditions = rule.get("conditions", [])
            if not conditions:
                continue

            # 1. Collect all unique timestamps for each condition dynamically
            ts_list = []
            for c in conditions:
                mask_c = rule_masks.get(c, pl.Series(values=[False] * batch.height))
                ts_list.append(batch.filter(mask_c)["timestamp"].unique())

            # 2. Apply AND / OR logic safely with runtime resilience
            logic = rule.get("logic", "UNKNOWN")

            if logic == "AND":
                if not ts_list:
                    continue
                target_ts = ts_list[0]
                for next_ts in ts_list[1:]:
                    target_ts = target_ts.filter(target_ts.is_in(next_ts))

            elif logic == "OR":
                if not ts_list:
                    continue
                target_ts = pl.concat(ts_list).unique()

            else:
                # Runtime Error Catch: Safe failure for Slurm jobs
                logger.error(
                    f"[SLURM RUNTIME ERROR] Unhandled logic '{logic}' for "
                    f"rule {rule['rule_id']}. Calculations for this rule will be skipped."
                )
                continue

            corr_mask = batch["timestamp"].is_in(target_ts)
            rule_masks[rule["rule_id"]] = corr_mask

            # 3. Dynamic Alarm Construction
            if len(target_ts) > 0:
                parent_sensors = [rule_to_sensor.get(c, "UNKNOWN") for c in conditions]
                sensor_str = ",".join(parent_sensors)

                corr_alarms = batch.filter(
                    corr_mask & batch["sensor_id"].is_in(parent_sensors)
                )

                if corr_alarms.height > 0:
                    # Dynamically build aggregation expressions for N sensors
                    agg_exprs = []
                    for i, s in enumerate(parent_sensors):
                        agg_exprs.append(
                            pl.col("value")
                            .filter(pl.col("sensor_id") == s)
                            .first()
                            .alias(f"val{i}")
                        )

                    grouped_corr = corr_alarms.group_by(
                        "timestamp", maintain_order=True
                    ).agg(agg_exprs)

                    # Dynamically build expressions for string casting and concatenation
                    val_cols = [f"val{i}" for i in range(len(parent_sensors))]
                    cast_exprs = [
                        pl.col(c).cast(pl.Utf8).fill_null("NaN") for c in val_cols
                    ]

                    grouped_corr = (
                        grouped_corr.with_columns(cast_exprs)
                        .with_columns(
                            pl.concat_str(
                                [pl.col(c) for c in val_cols], separator=","
                            ).alias("value")
                        )
                        .with_columns(
                            [
                                pl.lit(rule["rule_id"]).alias("rule_id"),
                                pl.lit(rule.get("priority", "HIGH")).alias("priority"),
                                pl.lit(sensor_str).alias("sensor_id"),
                            ]
                        )
                        .select(
                            ["timestamp", "rule_id", "priority", "sensor_id", "value"]
                        )
                    )

                    alarms_list.append(grouped_corr)

        # --- PHASE 3: Separation & Strict Sorting ---
        if not rule_masks:
            return batch, pl.DataFrame(
                schema={
                    "timestamp": pl.Utf8,
                    "rule_id": pl.Utf8,
                    "priority": pl.Utf8,
                    "sensor_id": pl.Utf8,
                    "value": pl.Utf8,
                }
            )

        mask_df = pl.DataFrame(rule_masks)
        combined_mask = mask_df.select(pl.any_horizontal(pl.all())).to_series()

        anomalous_ts = batch.filter(combined_mask)["timestamp"].unique()
        valid_telemetry = batch.filter(~batch["timestamp"].is_in(anomalous_ts))

        if alarms_list:
            alarm_telemetry = pl.concat(alarms_list)

            prio_map = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
            alarm_telemetry = (
                alarm_telemetry.with_columns(
                    pl.col("priority")
                    .replace(prio_map, return_dtype=pl.Int32)
                    .alias("sort_key")
                )
                .sort(
                    by=["timestamp", "sort_key", "rule_id", "sensor_id"],
                    descending=[False, True, False, False],
                )
                .drop("sort_key")
            )
        else:
            alarm_telemetry = pl.DataFrame(
                schema={
                    "timestamp": pl.Utf8,
                    "rule_id": pl.Utf8,
                    "priority": pl.Utf8,
                    "sensor_id": pl.Utf8,
                    "value": pl.Utf8,
                }
            )

        return valid_telemetry, alarm_telemetry
