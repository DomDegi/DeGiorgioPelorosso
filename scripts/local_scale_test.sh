#!/bin/bash
# Run this from the root of your DegiorgioPelorosso repository

echo "🚀 Starting Local Scalability Test..."

# Define datasets (Format -> "filename:row_count")
# Make sure these files exist in your csv_input/ directory
DATASETS=(
    "export_sat_alpha_custom_no_corruption.csv:1000000"
    "export_10X.csv:10000000"
    "export_25X.csv:25000000"
    "export_50X.csv:50000000"
    "export_100X.csv:100000000"
)

RESULTS_FILE="local_scalability_results.csv"
echo "Rows,Time_Seconds" > $RESULTS_FILE

# Ensure output directory exists
mkdir -p output

for DATASET in "${DATASETS[@]}"; do
    FILE="${DATASET%%:*}"
    ROWS="${DATASET##*:}"
    
    echo "================================================="
    echo "Testing dataset: $FILE ($ROWS rows)"
    
    if [ ! -f "inputs/csv_input/$FILE" ]; then
        echo "⚠️ Warning: inputs/csv_input/$FILE not found. Skipping."
        continue
    fi
    
    # Start timer
    START_TIME=$(date +%s)
    
    # Run the application locally using Python
    # (If you prefer running via your devcontainer, you can prepend 'docker exec -it <container_name>' here)
    python3 -m src.main \
        --batch_size 750000 \
        --input_path inputs/csv_input/$FILE \
        --output_path output \
        --rules_path inputs/config/Current_rules_sat_alpha.json \
        --sensors_path inputs/config/Current_sensors_sat_alpha.yaml

    # Stop timer
    END_TIME=$(date +%s)
    ELAPSED=$(($END_TIME - $START_TIME))
    
    echo "✅ Finished $FILE in $ELAPSED seconds."
    
    # Save the result
    echo "$ROWS,$ELAPSED" >> $RESULTS_FILE
    
    # Clean up output for the next iteration
    rm -rf output/*
done

echo "================================================="
echo "🎉 Local scalability test complete! Results saved to $RESULTS_FILE"
