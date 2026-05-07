import polars as pl
import os
from src.interfaces import IOutputWriter
import logging
logger = logging.getLogger(__name__)

class CSVOutputWriter(IOutputWriter):
    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        self.valid_path = os.path.join(output_dir, "valid_data.csv")
        self.alarms_path = os.path.join(output_dir, "alarms.log")
        os.makedirs(output_dir, exist_ok=True)
        
        # 1. Clean Slate Initialization
        for f in [self.valid_path, self.alarms_path]:
            if os.path.exists(f):
                os.remove(f)

    def write_valid_batch(self, batch: pl.DataFrame):
        if batch.height > 0:
            # Ordina per timestamp e sensore (ordine alfabetico richiesto)
            sorted_batch = batch.sort(["timestamp", "sensor_id"])
            
            # Raggruppa le misurazioni per timestamp, mantenendo l'ordine
            grouped = sorted_batch.group_by("timestamp", maintain_order=True).agg([
                pl.col("sensor_id"),
                pl.col("value")
            ])
            
            # Modalità 'a' (testo) invece di 'ab' (binario) per scrivere la stringa manuale
            with open(self.valid_path, 'a') as f:
                for row in grouped.iter_rows(named=True):
                    # Concatena le coppie SENSOR:VALUE con il pipe |
                    pairs = [f"{s}:{v}" for s, v in zip(row['sensor_id'], row['value'])]
                    payload = "|".join(pairs)
                    # Scrive nel file la stringa esatta
                    f.write(f"{row['timestamp']};NOMINAL;{payload}\n")

    def write_alarms_batch(self, alarms: pl.DataFrame):
        if alarms.height > 0:
            try:
                # Riordina le colonne esattamente come si aspetta il test (e la legacy)
                alarms_ordered = alarms.select(["timestamp", "rule_id", "priority", "sensor_id", "value"])
                
                with open(self.alarms_path, 'ab') as f:
                    alarms_ordered.write_csv(f, separator=";", has_header=not os.path.exists(self.alarms_path))
            except pl.exceptions.ColumnNotFoundError as e: # Cattura l'errore se mancano colonne
                logger.error(f"OutputWriter missing columns: {e}")
            except Exception as e:
                logger.error(f"OutputWriter missing columns: {e}")
