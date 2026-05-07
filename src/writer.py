import polars as pl
import os
from src.interfaces import IOutputWriter

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
        # 1. Multi-threaded CSV dump
        if batch.height > 0:
            with open(self.valid_path, 'ab') as f:
                # include_header only adds the header if the file is totally empty
                batch.write_csv(f, include_header=not os.path.exists(self.valid_path))

    def write_alarms_batch(self, alarms: pl.DataFrame):
        # 2. Custom Format Logging
        if alarms.height > 0:
            with open(self.alarms_path, 'ab') as f:
                # We use the separator argument to natively fulfill the semicolon requirement
                alarms.write_csv(f, separator=";", include_header=not os.path.exists(self.alarms_path))

```