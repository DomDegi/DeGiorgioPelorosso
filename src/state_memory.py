"""
State Tracking Component.

Provides high-speed, local memory solutions for tracking data across the 
boundaries of discrete batches, ensuring continuity for complex rules.
"""

from typing import Optional
from src.interfaces import IStateMemory

class DictStateMemory(IStateMemory):
    """
    In-memory implementation of the state tracker using standard Python dictionaries.
    
    Designed specifically for Single-Node High-Performance Computing (HPC). Using 
    dictionaries provides O(1) read/write access times, minimizing synchronization bottlenecks.
    """
    def __init__(self):
        """Initializes the underlying data structures for streaks and step values."""
        # Data structure: { "rule_id_sensor_id": integer_count }
        self._consecutive_counts = {}
        
        # Data structure: { "sensor_id": float_last_value }
        self._last_values = {}

    def _make_key(self, rule_id: str, sensor_id: str) -> str:
        """
        Private helper to create a unique dictionary key.
        
        Prevents collisions in memory between different rules that might be 
        monitoring the exact same sensor.

        Args:
            rule_id (str): The unique rule identifier.
            sensor_id (str): The unique sensor identifier.

        Returns:
            str: A combined unique key format.
        """
        return f"{rule_id}_{sensor_id}"

    # ==========================================
    # Stateful Rules Implementation
    # ==========================================
    def get_current_count(self, rule_id: str, sensor_id: str) -> int:
        """Retrieves the consecutive anomaly count, returning 0 if not found."""
        key = self._make_key(rule_id, sensor_id)
        return self._consecutive_counts.get(key, 0)

    def set_consecutive_count(self, rule_id: str, sensor_id: str, count: int) -> None:
        """Saves the final streak count for a sensor at the end of a batch."""
        key = self._make_key(rule_id, sensor_id)
        self._consecutive_counts[key] = count

    # ==========================================
    # Step Difference Rules Implementation
    # ==========================================
    def get_last_value(self, sensor_id: str) -> Optional[float]:
        """Retrieves the last recorded value of a sensor, returning None if not found."""
        return self._last_values.get(sensor_id, None)

    def set_last_value(self, sensor_id: str, value: float) -> None:
        """Saves the final value of a sensor at the end of a batch."""
        self._last_values[sensor_id] = value
