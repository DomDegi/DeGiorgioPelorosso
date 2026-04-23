"""
AstraLog-HPC Interfaces (Abstract Base Classes)

Differentiation of the used terminology:
- 'Batch': Refers to a logical unit of work processed in a single loop iteration 
  by the Orchestrator. It represents a discrete step in time.
- 'Chunk': Refers to the physical block of memory/data read from or written to 
  the disk by libraries like Pandas. (A 'chunk' of data becomes a 'batch' of work).
- 'Telemetry': The domain-specific aerospace term for the actual data payload 
  (e.g., sensor readings like VOLT-MAIN). We use this instead of generic "data".
"""

from abc import ABC, abstractmethod
from typing import Tuple
import pandas as pd


class ITelemetryReader(ABC):
    """
    Interface for the data ingestion component.
    
    Architecture Role:
    - Reason for Interface: Obscures the inner workings of how data is read from disk.
      By depending on this interface, the system doesn't care if the data comes from 
      a CSV, a JSON file, or an SQL Database. It makes unit testing trivial using Mocks.
    - Implemented by: `CSVTelemetryReader` (which will handle Pandas chunking).
    - Interfaced with: `BatchOrchestrator` (calls this to get the next block of work).
    """
    @abstractmethod
    def extract_batch(self, batch_size: int) -> pd.DataFrame:
        """
        Extracts the next physical 'chunk' of data from the source, sanitizes it, 
        and returns it as a logical 'batch' of clean telemetry.
        
        Args:
            batch_size (int): The maximum number of rows to read to prevent HPC memory overflow.
            
        Returns:
            pd.DataFrame: A batch of clean, validated telemetry ready for rule evaluation. 
                          Returns an empty DataFrame on EOF.
        """
        pass


class IRulesEngine(ABC):
    """
    Interface for the core business logic component.
    
    Architecture Role:
    - Reason for Interface: Decouples the Orchestrator from the mathematical and 
      stateful logic required to evaluate satellite rules. 
    - Implemented by: `PandasRulesEngine` (which will use vectorized C++ operations).
    - Interfaced with: `BatchOrchestrator` (passes raw telemetry in, gets evaluated telemetry out).
    """
    
    @abstractmethod
    def evaluate_rules(self, telemetry_batch: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Evaluates a batch of raw telemetry against the project rules (Simple, Stateful, etc.).
        
        Args:
            telemetry_batch (pd.DataFrame): The raw batch extracted by the Reader.
            
        Returns:
            Tuple[pd.DataFrame, pd.DataFrame]: A tuple containing two separated DataFrames:
                [0] valid_telemetry: Rows that triggered no alarms (Nominal/Valid).
                [1] alarm_telemetry: Rows that breached thresholds (Anomalies).
        """
        pass


class IStateMemory(ABC):
    """
    Interface for the memory tracking component.
    
    Architecture Role:
    - Reason for Interface: Stateful rules (e.g., "5 consecutive errors") require tracking
      data across multiple batches. This interface hides how that state is stored 
      (e.g., in a Python Dictionary, Redis, or Memcached).
    - Implemented by: `DictStateMemory` (stores state in local RAM).
    - Interfaced with: `PandasRulesEngine` (queries this component during rule evaluation).
    """
    
    @abstractmethod
    def increment_consecutive_count(self, rule_id: str, sensor_id: str) -> int:
        """Increments the anomaly counter for a specific sensor and returns the new count."""
        pass

    @abstractmethod
    def reset_consecutive_count(self, rule_id: str, sensor_id: str) -> None:
        """Resets the anomaly counter to zero when a sensor returns to a valid state."""
        pass

    @abstractmethod
    def get_current_count(self, rule_id: str, sensor_id: str) -> int:
        """Retrieves the current anomaly count without modifying the underlying state."""
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
    def write_valid_batch(self, valid_telemetry: pd.DataFrame) -> None:
        """
        Takes the logical batch of valid telemetry and appends it as a physical 
        chunk to the target storage (e.g., 'valid_data.csv').
        """
        pass

    @abstractmethod
    def write_alarms_batch(self, alarm_telemetry: pd.DataFrame) -> None:
        """
        Takes the logical batch of anomalies and appends it as a physical 
        chunk to the target storage (e.g., 'alarms.log').
        """
        pass
