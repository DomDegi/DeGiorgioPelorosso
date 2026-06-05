#!/bin/bash

# High-resolution sweep to plot a smooth U-Curve
BATCH_SIZES=(10000 25000 50000 75000 100000 150000 200000 250000 350000 500000 750000 1000000 1500000 2000000 2500000)
INPUT_FILE="inputs/csv_input/export_10X.csv"
OUTPUT_LOG="benchmark_results.csv"

# Create header for the results CSV
echo "Batch Size,Total Time (s),Max RAM (KB)" > $OUTPUT_LOG

for BATCH in "${BATCH_SIZES[@]}"; do
    echo "====================================="
    echo "Testing Batch Size: $BATCH"
    
    # We use /usr/bin/time to capture execution time (-e) and Max RAM (-M)
    # 2>&1 redirects the time output so we can capture it
    OUTPUT=$(/usr/bin/time -f "%e,%M" python3 -m src.main \
        --batch_size $BATCH \
        --input_path $INPUT_FILE \
        --output_path output \
        --rules_path inputs/config/Current_rules_sat_alpha.json \
        --sensors_path inputs/config/Current_sensors_sat_alpha.yaml 2>&1)

    # Extract the last line of the output which contains our "Time,RAM" string
    METRICS=$(echo "$OUTPUT" | tail -n 1)
    
    # Save to our CSV
    echo "$BATCH,$METRICS" >> $OUTPUT_LOG
    echo "Result saved: $BATCH,$METRICS"
done

echo "Benchmark complete! Check $OUTPUT_LOG"