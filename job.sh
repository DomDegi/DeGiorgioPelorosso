#!/bin/bash
#SBATCH --job-name=astralog_job
#SBATCH --account=tra26_TRNPLM
#SBATCH --partition=g100_usr_prod
#SBATCH --nodes=1
#SBATCH --cpus-per-task=32
#SBATCH --mem=64G
#SBATCH --time=00:15:00
#SBATCH --output=astralog_run_%j.log

echo "Starting job on compute node: $HOSTNAME"

SCRATCH_DIR="$WORK/astralog_run_$SLURM_JOB_ID"
mkdir -p $SCRATCH_DIR/inputs
mkdir -p $SCRATCH_DIR/output

echo "Moving data to high-speed storage..."
cp $HOME/inputs/export_100X.csv $SCRATCH_DIR/inputs/
cp $HOME/astralog-hpc.sif $SCRATCH_DIR/

export POLARS_MAX_THREADS=$SLURM_CPUS_PER_TASK

echo "Executing pipeline..."
singularity exec \
    --pwd /workspace \
    --bind $SCRATCH_DIR/inputs:/workspace/inputs \
    --bind $SCRATCH_DIR/output:/workspace/output \
    $SCRATCH_DIR/astralog-hpc.sif \
    python3 -m src.main \
    --batch_size 1599996 \ # About Thread_num * 50k (polars batch size) to maximize CPU utilization
    --input_path inputs/export_100X.csv \
    --output_path output \
    --rules_path config/Current_rules_sat_alpha.json \
    --sensors_path config/Current_sensors_sat_alpha.yaml

echo "Execution complete. Moving results back to home directory..."
cp -r $SCRATCH_DIR/output $HOME/astralog_results_$SLURM_JOB_ID/

rm -rf $SCRATCH_DIR
echo "Job finished successfully!"