"""
AstraLog-HPC Interfaces (Abstract Base Classes).

This module defines the architectural contracts for the AstraLog-HPC system.
By relying on these interfaces, the orchestrator is decoupled from the underlying
implementations, enabling modularity, easy swapping of components, and mock-based testing.

Terminology:
- **Batch**: A logical unit of work processed in a single loop iteration by the Orchestrator.
- **Chunk**: A physical block of memory/data read from or written to the disk.
- **Telemetry**: The domain-specific term for the actual data payload (e.g., sensor readings).
"""

from abc import ABC, abstractmethod
from typing import Tuple, Optional
import polars as pl


class ITelemetryReader(ABC):
    """
    Interface for the data ingestion component.
    
    Obscures the inner workings of how data is read from disk. By depending on this 
    interface, the system can seamlessly switch between CSV, JSON, or SQL databases.
    """
    
    @abstractmethod
    def extract_batch(self, batch_size: int) -> pl.DataFrame:
        """
        Extracts the next physical chunk of data, sanitizes it, and returns a logical batch.
        
        Args:
            batch_size (int): The maximum number of rows to read, preventing HPC memory overflow.
            
        Returns:
            pl.DataFrame: A batch of clean, validated telemetry ready for rule evaluation. 
                Returns an empty DataFrame when the end of the file/stream is reached.
        """
        pass


class IRulesEngine(ABC):
    """
    Interface for the core business logic component.
    
    Decouples the Orchestrator from the mathematical and stateful logic required 
    to evaluate satellite monitoring rules.
    """
    
    @abstractmethod
    def evaluate_rules(self, telemetry_batch: pl.DataFrame) -> Tuple[pl.DataFrame, pl.DataFrame]:
        """
        Evaluates a batch of raw telemetry against the project rules (Simple, Stateful, etc.).
        
        Args:
            telemetry_batch (pl.DataFrame): The raw batch extracted by the Reader.
            
        Returns:
            Tuple[pl.DataFrame, pl.DataFrame]: A tuple containing two DataFrames:
                - `valid_telemetry`: Rows that triggered no alarms (Nominal).
                - `alarm_telemetry`: Rows that breached thresholds (Anomalies).
        """
        pass


class IStateMemory(ABC):
    """
    Interface for the memory tracking component.
    
    Stateful rules (e.g., "5 consecutive errors") and Step rules require tracking 
    data across multiple batches. This interface hides how the state is physically stored.
    """
    
    @abstractmethod
    def get_current_count(self, rule_id: str, sensor_id: str) -> int:
        """
        Retrieves the consecutive anomaly count carried over from the previous batch.

        Args:
            rule_id (str): The ID of the stateful rule.
            sensor_id (str): The ID of the monitored sensor.

        Returns:
            int: The current consecutive anomaly count.
        """
        pass

    @abstractmethod
    def set_consecutive_count(self, rule_id: str, sensor_id: str, count: int) -> None:
        """
        Overwrites the anomaly counter with the final calculated streak of the current batch.

        Args:
            rule_id (str): The ID of the stateful rule.
            sensor_id (str): The ID of the monitored sensor.
            count (int): The final consecutive anomaly count to store.
        """
        pass

    @abstractmethod
    def get_last_value(self, sensor_id: str) -> Optional[float]:
        """
        Retrieves the absolute value of the sensor recorded at the very end of the last batch.

        Args:
            sensor_id (str): The ID of the monitored sensor.

        Returns:
            Optional[float]: The last recorded float value, or None if no previous record exists.
        """
        pass

    @abstractmethod
    def set_last_value(self, sensor_id: str, value: float) -> None:
        """
        Saves the final value of the sensor in the current batch to be used in the next one.

        Args:
            sensor_id (str): The ID of the monitored sensor.
            value (float): The final sensor value of the current batch.
        """
        pass


class IOutputWriter(ABC):
    """
    Interface for the data exportation component.
    
    Obscures how and where the final results are saved, preventing the Orchestrator 
    from being tied to specific file paths or formats.
    """
    
    @abstractmethod
    def write_valid_batch(self, valid_telemetry: pl.DataFrame) -> None:
        """
        Takes the logical batch of valid telemetry and appends it to the target storage.

        Args:
            valid_telemetry (pl.DataFrame): The nominal data cleared by the Rules Engine.
        """
        pass

    @abstractmethod
    def write_alarms_batch(self, alarm_telemetry: pl.DataFrame) -> None:
        """
        Takes the logical batch of anomalies and appends it to the target storage.

        Args:
            alarm_telemetry (pl.DataFrame): The anomalous data flagged by the Rules Engine.
        """
        pass