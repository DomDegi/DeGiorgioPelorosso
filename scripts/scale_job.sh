#!/bin/bash
#SBATCH --job-name=astralog_scale
#SBATCH --account=tra26_TRNPLM
#SBATCH --partition=g100_usr_prod
#SBATCH --nodes=1
#SBATCH --cpus-per-task=32
#SBATCH --mem=64G
#SBATCH --time=01:00:00  # Increased time since we are running multiple files
#SBATCH --output=astralog_scale_%j.log

echo "Starting scalability test on compute node: $HOSTNAME"

# 1. Define the files you want to test and the number of rows they contain.
# Format: "filename:row_count"
DATASETS=(
    "export_sat_alpha_custom_no_corruption.csv:1000000"
    "export_10X.csv:10000000"
    "export_25X.csv:25000000"
    "export_50X.csv:50000000"
    "export_100X.csv:100000000"
)

# Set up Scratch and output file
SCRATCH_DIR="$WORK/astralog_scale_$SLURM_JOB_ID"
RESULTS_FILE="$HOME/scalability_results.csv"

# create all required subdirectories
mkdir -p $SCRATCH_DIR/inputs/config
mkdir -p $SCRATCH_DIR/inputs/csv_input
mkdir -p $SCRATCH_DIR/output

# Initialize the results CSV with headers
echo "Rows,Time_Seconds" > $RESULTS_FILE

echo "Copying config files and Singularity container..."
cp $HOME/inputs/config/*.json $SCRATCH_DIR/inputs/config/
cp $HOME/inputs/config/*.yaml $SCRATCH_DIR/inputs/config/
cp $HOME/astralog-hpc.sif $SCRATCH_DIR/

export POLARS_MAX_THREADS=$SLURM_CPUS_PER_TASK

# Move into the scratch directory for safe execution
cd $SCRATCH_DIR

# 2. Loop through each dataset
for DATASET in "${DATASETS[@]}"; do
    # Extract filename and row count using string manipulation
    FILE="${DATASET%%:*}"
    ROWS="${DATASET##*:}"

    echo "================================================="
    echo "Testing dataset: $FILE ($ROWS rows)"

    # Copy the specific CSV to scratch
    cp $HOME/inputs/csv_input/$FILE $SCRATCH_DIR/inputs/csv_input/

    # Start timer
    START_TIME=$(date +%s)

    # Run the pipeline (using your optimal batch size of 200,000)
    singularity exec \
        --pwd /workspace \
        --bind $SCRATCH_DIR/inputs:/workspace/inputs \
        --bind $SCRATCH_DIR/output:/workspace/output \
        astralog-hpc.sif \
        python3 -m src.main \
        --batch_size 200000 \
        --input_path inputs/csv_input/$FILE \
        --output_path output \
        --rules_path inputs/config/Current_rules_sat_alpha.json \
        --sensors_path inputs/config/Current_sensors_sat_alpha.yaml

    # Stop timer
    END_TIME=$(date +%s)
    ELAPSED=$(($END_TIME - $START_TIME))

    echo "Finished $FILE in $ELAPSED seconds."

    # Save the result to our tracking CSV
    echo "$ROWS,$ELAPSED" >> $RESULTS_FILE

    # Clean up the output folder so the next run starts fresh
    rm -rf $SCRATCH_DIR/output/*

    # Remove the specific CSV to free up space for the next loop
    rm $SCRATCH_DIR/inputs/csv_input/$FILE
done

echo "================================================="
echo "Scalability test complete! Results saved to ~/scalability_results.csv"

# Go back to HOME before deleting the scratch directory
cd $HOME
rm -rf $SCRATCH_DIR
