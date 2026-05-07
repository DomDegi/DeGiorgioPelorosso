#!/bin/bash

# Termina immediatamente lo script se c'è un errore
set -e

echo "🚀 Start AstraLog-HPC Orchestrator..."
echo "========================================="

# --- CONFIG ---
BATCH_SIZE=10000
INPUT_CSV="csv_input/export_sat_alpha_custom.csv"
OUTPUT_DIR="output"
RULES_JSON="config/Current_rules_sat_alpha.json"
SENSORS_YAML="config/Current_sensors_sat_alpha.yaml"
# ----------------------

mkdir -p "$OUTPUT_DIR"

python3 -m src.main \
  --batch_size "$BATCH_SIZE" \
  --input_path "$INPUT_CSV" \
  --output_path "$OUTPUT_DIR" \
  --rules_path "$RULES_JSON" \
  --sensors_path "$SENSORS_YAML"

echo "========================================="
echo "Success!"
echo "Results available in: $OUTPUT_DIR/"