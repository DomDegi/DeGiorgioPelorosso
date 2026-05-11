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

# Definisci il nome del file CSV qui, così non puoi sbagliare a scriverlo sotto
CSV_FILENAME="export_sat_alpha_custom_no_corruption.csv"

SCRATCH_DIR="$WORK/astralog_run_$SLURM_JOB_ID"
mkdir -p $SCRATCH_DIR/inputs
mkdir -p $SCRATCH_DIR/output

echo "Moving data to high-speed storage..."
# Copia i file usando la variabile per il CSV e copiando i JSON/YAML
cp $HOME/inputs/$CSV_FILENAME $SCRATCH_DIR/inputs/
cp $HOME/inputs/*.json $SCRATCH_DIR/inputs/
cp $HOME/inputs/*.yaml $SCRATCH_DIR/inputs/
cp $HOME/astralog-hpc.sif $SCRATCH_DIR/

export POLARS_MAX_THREADS=$SLURM_CPUS_PER_TASK

echo "Executing pipeline..."
singularity exec \
    --pwd /workspace \
    --bind $SCRATCH_DIR/inputs:/workspace/inputs \
    --bind $SCRATCH_DIR/output:/workspace/output \
    $SCRATCH_DIR/astralog-hpc.sif \
    python3 -m src.main \
    --batch_size 1599996 \
    --input_path inputs/$CSV_FILENAME \
    --output_path output \
    --rules_path inputs/Current_rules_sat_alpha.json \
    --sensors_path inputs/Current_sensors_sat_alpha.yaml

echo "Execution complete. Moving results back to home directory..."
mkdir -p $HOME/astralog_results_$SLURM_JOB_ID
cp -r $SCRATCH_DIR/output/* $HOME/astralog_results_$SLURM_JOB_ID/

rm -rf $SCRATCH_DIR
echo "Job finished successfully!"