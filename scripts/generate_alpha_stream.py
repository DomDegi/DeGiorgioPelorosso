import pandas as pd
import numpy as np
import yaml
import json
import os
import time
import random

def generate_mission_dataset(sensors_path: str, rules_path: str, output_path: str, num_timestamps: int = 100_000):
    print(f"🚀 Avvio generazione dati basata su {sensors_path} e {rules_path}...")
    start_time = time.perf_counter()

    # 1. LEGGE I FILE DI CONFIGURAZIONE
    with open(sensors_path, 'r') as f:
        yaml_data = yaml.safe_load(f)
        sensor_ids = [s['id'] for s in yaml_data['sensors']]
    
    with open(rules_path, 'r') as f:
        rules = json.load(f)

    num_sensors = len(sensor_ids)
    num_rows = num_timestamps * num_sensors
    print(f"📡 Sensori trovati: {num_sensors}. Generazione di {num_rows:,} righe totali...")

    # 2. GENERAZIONE VETTORIALIZZATA (Veloce)
    # Crea i timestamp (1 secondo di distanza)
    start_date = pd.Timestamp("2026-05-01T00:00:00Z")
    date_range = pd.date_range(start_date, periods=num_timestamps, freq='S')
    
    # Ripete ogni timestamp per il numero di sensori (DA-3: tutti i sensori misurano allo stesso istante)
    timestamps_col = np.repeat(date_range, num_sensors)
    
    # Cicla l'array dei sensori per ogni timestamp
    sensors_col = np.tile(sensor_ids, num_timestamps)
    
    # Genera priorità e valori base
    priorities_col = np.random.choice(['HIGH', 'MEDIUM', 'LOW'], num_rows)
    # Valori base attorno a 60 con deviazione standard di 15
    values_col = np.random.normal(loc=60.0, scale=15.0, size=num_rows)

    df = pd.DataFrame({
        'timestamp': timestamps_col.strftime('%Y-%m-%dT%H:%M:%SZ'),
        'sensor_id': sensors_col,
        'value': values_col,
        'priority': priorities_col
    })

    # 3. INIEZIONE MIRATA DI ANOMALIE (Basata su rules.json)
    print("🎯 Iniezione di anomalie matematiche per attivare le regole...")
    # Leggiamo alcune soglie dalle regole per forzare degli allarmi
    for rule in rules:
        if rule['type'] in ['simple', 'stateful']:
            # Troviamo gli indici di questo sensore
            target_sensor_idx = df[df['sensor_id'] == rule['sensor_id']].index
            
            # Selezioniamo casualmente il 2% delle letture di questo sensore per farle sballare
            anomaly_idx = np.random.choice(target_sensor_idx, size=int(len(target_sensor_idx) * 0.02), replace=False)
            
            # Applichiamo un valore che rompe la regola
            if rule['operator'] == '>':
                df.loc[anomaly_idx, 'value'] = rule['value'] + 20.0 # Valore sopra la soglia
            elif rule['operator'] == '<':
                df.loc[anomaly_idx, 'value'] = rule['value'] - 20.0 # Valore sotto la soglia

    # 4. INIEZIONE DI ERRORI STRUTTURALI (Per testare il CorruptionCheck)
    print("🦠 Iniezione di errori di formato (schema e tipo)...")
    error_indices = np.random.choice(num_rows, size=5000, replace=False)
    
    for idx in error_indices:
        error_type = random.choice(['schema_missing', 'type_string'])
        if error_type == 'schema_missing':
            df.loc[idx, 'priority'] = pd.NA  # Manca un campo
        else:
            df.loc[idx, 'value'] = "GLITCH_OR_NIL" # Errore di tipo

    # 5. SALVATAGGIO
    print("💾 Salvataggio dei dati su disco...")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df.to_csv(output_path, index=False)

    # 6. INIEZIONE DI PACKET CORROTTI A LIVELLO FISICO
    print("💥 Aggiunta di stringhe CSV malformate alla fine del file...")
    with open(output_path, 'a') as f:
        f.write('2026-05-01T23:59:58Z,TEMP-001,25.5\n') # Manca un campo intero (niente virgola)
        f.write('2026-05-01T23:59:59Z,PRES-002,101.3,"HIGH\n') # Errore di parsing (virgolette non chiuse)
        f.write('GARBAGE_NOISE_TRANSMISSION_LOST\n') # Spazzatura

    end_time = time.perf_counter()
    file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
    
    print("=========================================")
    print("✅ DATASET DELLA MISSIONE PRONTO!")
    print(f"Sensori       : {num_sensors}")
    print(f"Timestamp Unici: {num_timestamps:,}")
    print(f"Righe Totali  : {num_rows:,}")
    print(f"Dimensione    : {file_size_mb:.2f} MB")
    print(f"Tempo Gen.    : {end_time - start_time:.2f} sec")
    print(f"Salvato in    : {output_path}")
    print("=========================================")

if __name__ == "__main__":
    generate_mission_dataset(
        sensors_path="config/Current_sensors_sat_alpha.yaml",
        rules_path="config/Current_rules_sat_alpha.json",
        output_path="csv_input/export_sat_alpha_custom.csv",
        num_timestamps=83334 # Circa 1 milione di righe totali (83334 * 12 sensori)
    )
