#!/bin/bash

# Configuration
INPUT_FILE="export_sat_alpha_custom_no_corruption.csv"
X_TIMES=100  # Change this to however many times you want to copy the file

# Dynamically set the output file name based on the X_TIMES variable
OUTPUT_FILE="export_${X_TIMES}X.csv"

echo "Starting CSV duplication. Creating $OUTPUT_FILE..."

# 1. Copy the file the first time (this includes the header)
cat "$INPUT_FILE" > "$OUTPUT_FILE"
echo "Copied iteration 1 (with header)..."

# 2. Loop for the remaining (X - 1) times, skipping the first line (the header)
for ((i=2; i<=X_TIMES; i++)); do
    # 'tail -n +2' outputs everything starting from line 2 (skipping the header)
    tail -n +2 "$INPUT_FILE" >> "$OUTPUT_FILE"
    
    echo "Copied iteration $i..."
done

echo "Done! Clean CSV created: $OUTPUT_FILE"