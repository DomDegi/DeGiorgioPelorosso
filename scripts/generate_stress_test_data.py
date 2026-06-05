import polars as pl
import numpy as np
import random
import os
import time

def generate_massive_dataset(num_rows: int = 1_000_000, output_path: str = "input/export_sat_alpha_massive.csv"):
    print(f"🚀 Generating {num_rows:,} rows of satellite telemetry. Please wait...")
    start_time = time.perf_counter()

    # 1. GENERATE BASE DATA FAST (Using NumPy)
    # Generate timestamps (1 second apart)
    start_date = pl.Timestamp("2026-04-24T00:00:00Z")
    timestamps = [start_date + pl.Timedelta(seconds=i) for i in range(num_rows)]

    # Generate random sensors and priorities
    sensors = ['TEMP-01', 'PRES-01', 'VOLT-MAIN']
    priorities = ['HIGH', 'MEDIUM', 'LOW']
    
    sensor_col = np.random.choice(sensors, num_rows)
    priority_col = np.random.choice(priorities, num_rows)
    
    # Generate nominal values (mostly normal, occasionally spiking)
    value_col = np.random.normal(loc=25.0, scale=2.0, size=num_rows)
    
    # Intentionally inject some mathematical anomalies (Values > 50, Drops, etc.)
    # Make ~1% of the data anomalous
    anomaly_indices = np.random.choice(num_rows, size=int(num_rows * 0.01), replace=False)
    value_col[anomaly_indices] = np.random.choice([60.0, 10.0, -5.0, 100.0], size=len(anomaly_indices))

    # Create the DataFrame
    df = pl.DataFrame({
        'timestamp': timestamps,
        'sensor_id': sensor_col,
        'value': value_col,
        'priority': priority_col
    })

    # 2. INJECT STRUCTURAL ERRORS (Schema & Type)
    print("🦠 Injecting Schema and Type errors...")
    error_indices = np.random.choice(num_rows, size=5000, replace=False)
    
    for idx in error_indices:
        error_type = random.choice(['schema_missing', 'type_string'])
        if error_type == 'schema_missing':
            # Schema Error: Missing mandatory priority
            df.loc[idx, 'priority'] = pd.NA 
        else:
            # Type Error: String instead of float
            df.loc[idx, 'value'] = "SENSOR_GLITCH"

    # 3. SAVE TO DISK
    print("💾 Saving clean & logical errors to CSV...")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df.to_csv(output_path, index=False)

    # 4. INJECT MALFORMED LINES (Physical CSV Corruption)
    print("💥 Appending physically malformed strings (truncated data)...")
    with open(output_path, 'a') as f:
        f.write('2026-04-24T23:59:58Z,TEMP-01,25.5\n') # Missing comma/priority
        f.write('2026-04-24T23:59:59Z,PRES-01,101.3,"HIGH\n') # Unclosed quote
        f.write('GARBAGE_DATA_TRANSMISSION_INTERRUPTED\n') # Complete garbage

    end_time = time.perf_counter()
    file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
    
    print("=========================================")
    print("✅ STRESS TEST DATASET READY!")
    print(f"Total Rows : {num_rows:,}")
    print(f"File Size  : {file_size_mb:.2f} MB")
    print(f"Gen Time   : {end_time - start_time:.2f} seconds")
    print(f"Saved to   : {output_path}")
    print("=========================================")

if __name__ == "__main__":
    generate_massive_dataset()
