import pandas as pd
import numpy as np
import yaml
import json
import os
import time
import random

def generate_mission_dataset(sensors_path: str, rules_path: str, output_path: str, num_timestamps: int = 100_000):
    print(f"Start generation dataset based on {sensors_path} and {rules_path}...")
    start_time = time.perf_counter()

    # 1. READ CONFIG FILES
    with open(sensors_path, 'r') as f:
        yaml_data = yaml.safe_load(f)
        sensor_ids = [s['id'] for s in yaml_data['sensors']]
    
    with open(rules_path, 'r') as f:
        rules = json.load(f)

    num_sensors = len(sensor_ids)
    num_rows = num_timestamps * num_sensors
    print(f"Sensors found: {num_sensors}. Generating {num_rows:,} rows total...")

    # 2. VECTORIZED GENERATION (Fast)
    # Create timestamps (1 second apart)
    start_date = pd.Timestamp("2026-05-01T00:00:00Z")
    date_range = pd.date_range(start_date, periods=num_timestamps, freq='S')
    
    # Repeat each timestamp for number of sensors (DA-3: all sensors measure at the same instant)
    timestamps_col = np.repeat(date_range, num_sensors)
    
    # Cycle the sensor array for each timestamp
    sensors_col = np.tile(sensor_ids, num_timestamps)
    
    # Generate priorities and base values
    priorities_col = np.random.choice(['HIGH', 'MEDIUM', 'LOW'], num_rows)
    # Base values around 60 with standard deviation of 15
    values_col = np.random.normal(loc=60.0, scale=15.0, size=num_rows)

    df = pd.DataFrame({
        'timestamp': timestamps_col.strftime('%Y-%m-%dT%H:%M:%SZ'),
        'sensor_id': sensors_col,
        'value': values_col,
        'priority': priorities_col
    })

    # 3. INJECTION OF TARGETED ANOMALIES (Based on rules.json)
    print("Injecting targeted anomalies...")
    # Read some thresholds from the rules to force alarms
    for rule in rules:
        if rule['type'] in ['simple', 'stateful']:
            # Troviamo gli indici di questo sensore
            # Find indices for this sensor
            target_sensor_idx = df[df['sensor_id'] == rule['sensor_id']].index
            
            # Randomly select 2% of this sensor's readings to corrupt
            anomaly_idx = np.random.choice(target_sensor_idx, size=int(len(target_sensor_idx) * 0.02), replace=False)
            
            # Applichiamo un valore che rompe la regola
            # Apply a value that breaks the rule
            if rule['operator'] == '>':
                df.loc[anomaly_idx, 'value'] = rule['value'] + 20.0 # Value above the threshold
            elif rule['operator'] == '<':
                df.loc[anomaly_idx, 'value'] = rule['value'] - 20.0 # Value below the threshold

    # 4. INJECTION OF STRUCTURAL ERRORS (To test CorruptionCheck)
    print("🦠 Injecting format errors (schema and type)...")
    error_indices = np.random.choice(num_rows, size=5000, replace=False)
    
    for idx in error_indices:
        error_type = random.choice(['schema_missing', 'type_string'])
        if error_type == 'schema_missing':
            df.loc[idx, 'priority'] = pd.NA  # Missing a field
        else:
            df.loc[idx, 'value'] = "GLITCH_OR_NIL" # Type error

    # 5. SAVING
    print("💾 Saving data to disk...")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df.to_csv(output_path, index=False)

    # 6. INJECTION OF CORRUPTED PHYSICAL PACKETS
    print("💥 Appending malformed CSV strings to the end of the file...")
    with open(output_path, 'a') as f:
        f.write('2026-05-01T23:59:58Z,TEMP-001,25.5\n') # Missing priority (schema error)
        f.write('2026-05-01T23:59:59Z,PRES-002,101.3,"HIGH\n') # Parsing error (unclosed quote)
        f.write('GARBAGE_NOISE_TRANSMISSION_LOST\n') # Garbage

    end_time = time.perf_counter()
    file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
    
    print("=========================================")
    print("MISSION DATASET READY!")
    print(f"Sensors       : {num_sensors}")
    print(f"Unique Timestamps: {num_timestamps:,}")
    print(f"Total Rows    : {num_rows:,}")
    print(f"Size          : {file_size_mb:.2f} MB")
    print(f"Generation Time: {end_time - start_time:.2f} sec")
    print(f"Saved to      : {output_path}")
    print("=========================================")

if __name__ == "__main__":
    generate_mission_dataset(
        sensors_path="inputs/config/Current_sensors_sat_alpha.yaml",
        rules_path="inputs/config/Current_rules_sat_alpha.json",
        output_path="inputs/csv_input/export_sat_alpha_custom.csv",
        num_timestamps=83334 # About 1 million total rows (83334 * 12 sensors)
    )
