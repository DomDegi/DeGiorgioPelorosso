#!/bin/bash
#SBATCH --job-name=astra_batch_bench
#SBATCH --account=tra26_TRNPLM
#SBATCH --partition=g100_usr_prod
#SBATCH --nodes=1
#SBATCH --cpus-per-task=32
#SBATCH --mem=64G
#SBATCH --time=02:00:00
#SBATCH --output=astralog_batch_bench_%j.log

echo "Starting Batch Size Benchmark on compute node: $HOSTNAME"

# Choose a fixed dataset to benchmark against (e.g., your large dataset)
DATASET="export_10X.csv"
RESULTS_FILE="$HOME/benchmark_results_reproduced.csv"

# The batch sizes you tested in your original benchmark
BATCH_SIZES=(10000 25000 50000 75000 100000 150000 200000 250000 350000 500000 750000 1000000 1500000 2000000 2500000)

# Initialize CSV with exact headers from your docs
echo "Batch Size,Total Time (s),Max RAM (KB)" > $RESULTS_FILE

# Set up Scratch directories
SCRATCH_DIR="$WORK/astra_bench_$SLURM_JOB_ID"
mkdir -p $SCRATCH_DIR/inputs
mkdir -p $SCRATCH_DIR/output

echo "Copying files to high-speed scratch storage..."
cp $HOME/inputs/*.json $SCRATCH_DIR/inputs/
cp $HOME/inputs/*.yaml $SCRATCH_DIR/inputs/
cp $HOME/inputs/$DATASET $SCRATCH_DIR/inputs/
cp $HOME/astralog-hpc.sif $SCRATCH_DIR/

export POLARS_MAX_THREADS=$SLURM_CPUS_PER_TASK

for BATCH in "${BATCH_SIZES[@]}"; do
    echo "================================================="
    echo "Testing Batch Size: $BATCH"
    
    # We use /usr/bin/time to capture memory and execution time
    # %e = Elapsed wall clock time in seconds
    # %M = Maximum resident set size in Kilobytes
    # The output is directed to a temporary file so we can parse it easily
    TIME_LOG="$SCRATCH_DIR/time_${BATCH}.log"
    
    /usr/bin/time -f "%e,%M" -o $TIME_LOG singularity exec \
        --pwd /workspace \
        --bind $SCRATCH_DIR/inputs:/workspace/inputs \
        --bind $SCRATCH_DIR/output:/workspace/output \
        $SCRATCH_DIR/astralog-hpc.sif \
        python3 -m src.main \
        --batch_size $BATCH \
        --input_path inputs/$DATASET \
        --output_path output \
        --rules_path inputs/Current_rules_sat_alpha.json \
        --sensors_path inputs/Current_sensors_sat_alpha.yaml
        
    # Read the formatted output from /usr/bin/time
    METRICS=$(cat $TIME_LOG)
    
    # Append the results: BatchSize,Time(s),Memory(KB)
    echo "$BATCH,$METRICS" >> $RESULTS_FILE
    
    echo "Result: $BATCH,$METRICS"
    
    # Clean up output for the next batch run
    rm -rf $SCRATCH_DIR/output/*
done

echo "================================================="
echo "🎉 Benchmark complete! Results saved to ~/benchmark_results_reproduced.csv"
rm -rf $SCRATCH_DIR
