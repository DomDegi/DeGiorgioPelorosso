"""
AstraLog-HPC Interfaces (Abstract Base Classes)

Differentiation of the used terminology:
- 'Batch': Refers to a logical unit of work processed in a single loop iteration 
  by the Orchestrator. It represents a discrete step in time.
- 'Chunk': Refers to the physical block of memory/data read from or written to 
  the disk by libraries like Pandas/Polars. (A 'chunk' of data becomes a 'batch' of work).
- 'Telemetry': The domain-specific aerospace term for the actual data payload 
  (e.g., sensor readings like VOLT-MAIN). We use this instead of generic "data".
"""

from abc import ABC, abstractmethod
from typing import Tuple, Optional
import polars as pl


class ITelemetryReader(ABC):
    """
    Interface for the data ingestion component.
    
    Architecture Role:
    - Reason for Interface: Obscures the inner workings of how data is read from disk.
      By depending on this interface, the system doesn't care if the data comes from 
      a CSV, a JSON file, or an SQL Database. It makes unit testing trivial using Mocks.
    - Implemented by: `CSVTelemetryReader`.
    - Interfaced with: `BatchOrchestrator` (calls this to get the next block of work).
    """
    @abstractmethod
    def extract_batch(self, batch_size: int) -> pl.DataFrame:
        """
        Extracts the next physical 'chunk' of data from the source, sanitizes it, 
        and returns it as a logical 'batch' of clean telemetry.
        
        Args:
            batch_size (int): The maximum number of rows to read to prevent HPC memory overflow.
            
        Returns:
            pl.DataFrame: A batch of clean, validated telemetry ready for rule evaluation. 
                          Returns an empty DataFrame on EOF.
        """
        pass


class IRulesEngine(ABC):
    """
    Interface for the core business logic component.
    
    Architecture Role:
    - Reason for Interface: Decouples the Orchestrator from the mathematical and 
      stateful logic required to evaluate satellite rules. 
    - Implemented by: `PolarsRulesEngine` (which will use vectorized Rust operations).
    - Interfaced with: `BatchOrchestrator` (passes raw telemetry in, gets evaluated telemetry out).
    """
    
    @abstractmethod
    def evaluate_rules(self, telemetry_batch: pl.DataFrame) -> Tuple[pl.DataFrame, pl.DataFrame]:
        """
        Evaluates a batch of raw telemetry against the project rules (Simple, Stateful, etc.).
        
        Args:
            telemetry_batch (pl.DataFrame): The raw batch extracted by the Reader.
            
        Returns:
            Tuple[pl.DataFrame, pl.DataFrame]: A tuple containing two separated DataFrames:
                [0] valid_telemetry: Rows that triggered no alarms (Nominal/Valid).
                [1] alarm_telemetry: Rows that breached thresholds (Anomalies).
        """
        pass


class IStateMemory(ABC):
    """
    Interface for the memory tracking component.
    
    Architecture Role:
    - Reason for Interface: Stateful rules (e.g., "5 consecutive errors") and Step rules 
      require tracking data across multiple batches. This hides how state is stored.
    - Implemented by: `DictStateMemory` (stores state in local RAM).
    - Interfaced with: `PolarsRulesEngine` (queries this component during rule evaluation).
    """
    
    # --- For the Stateful Rules (Consecutive alerts) ---
    @abstractmethod
    def get_current_count(self, rule_id: str, sensor_id: str) -> int:
        """Retrieves the current anomaly count carried over from the previous batch."""
        pass

    @abstractmethod
    def set_consecutive_count(self, rule_id: str, sensor_id: str, count: int) -> None:
        """Overwrites the anomaly counter with the final calculated streak of the current batch."""
        pass

    # --- For the Step Difference Rules (T_n - T_{n-1}) ---
    @abstractmethod
    def get_last_value(self, sensor_id: str) -> Optional[float]:
        """Retrieves the absolute value of the sensor recorded at the very end of the last batch."""
        pass

    @abstractmethod
    def set_last_value(self, sensor_id: str, value: float) -> None:
        """Saves the final value of the sensor in the current batch to be used in the next one."""
        pass

class IOutputWriter(ABC):
    """
    Interface for the data exportation component.
    
    Architecture Role:
    - Reason for Interface: Obscures how and where the final results are saved. 
      Prevents the Orchestrator from being tied to specific file paths or file types.
    - Implemented by: `CSVOutputWriter` (appends physical chunks to output CSVs).
    - Interfaced with: `BatchOrchestrator` (sends the separated DataFrames here to be saved).
    """
    
    @abstractmethod
    def write_valid_batch(self, valid_telemetry: pl.DataFrame) -> None:
        """
        Takes the logical batch of valid telemetry and appends it as a physical 
        chunk to the target storage (e.g., 'valid_data.csv').
        """
        pass

    @abstractmethod
    def write_alarms_batch(self, alarm_telemetry: pl.DataFrame) -> None:
        """
        Takes the logical batch of anomalies and appends it as a physical 
        chunk to the target storage (e.g., 'alarms.log').
        """
        pass