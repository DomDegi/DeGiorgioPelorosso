#!/bin/bash

# Configuration
INPUT_FILE="../inputs/csv_input/export_sat_alpha_custom_no_corruption.csv"

# The specific multiples you need for your scalability plot
MULTIPLIERS=(10 25 50 100)

echo "🚀 Starting specific CSV generation for plot datasets..."

# Extract header and body to temporary files just once for maximum speed
TMP_HEADER=$(mktemp)
TMP_BODY=$(mktemp)

# Get the first line (header)
head -n 1 "$INPUT_FILE" > "$TMP_HEADER"
# Get everything except the first line (body)
tail -n +2 "$INPUT_FILE" > "$TMP_BODY"

# Loop through only the specific values in the list
for M in "${MULTIPLIERS[@]}"; do
    OUTPUT_FILE="../inputs/csv_input/export_${M}X.csv"
    echo "⏳ Creating $OUTPUT_FILE (multiplying body ${M} times)..."

    # 1. Start by placing the header into the new file
    cat "$TMP_HEADER" > "$OUTPUT_FILE"

    # 2. Append the body exactly M times
    for ((i=1; i<=M; i++)); do
        cat "$TMP_BODY" >> "$OUTPUT_FILE"
    done

    echo "✅ Finished generating $OUTPUT_FILE"
done

# Clean up temporary files
rm "$TMP_HEADER" "$TMP_BODY"

echo "🎉 Done! All requested plot datasets have been generated."
