#!/bin/bash
#SBATCH --job-name=astralog_job
#SBATCH --account=tra26_TRNPLM
#SBATCH --partition=g100_usr_prod
#SBATCH --time=00:30:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=4GB
#SBATCH --output=astralog_output.txt
#SBATCH --error=astralog_error.txt

echo "Starting AstroLog job on Galileo100 from HOME directory..."

module load singularity

IMAGE_NAME="astralog-hpc.sif"
IMAGE_URL="docker://ghcr.io/domdegi/astralog-hpc:latest"

# 1. Pull the image if missing
if [ ! -f "$IMAGE_NAME" ]; then
    echo "Pulling from $IMAGE_URL..."
    singularity pull $IMAGE_NAME $IMAGE_URL
fi

# 2. Create local directories to prevent Singularity mount crashes
mkdir -p $HOME/inputs
mkdir -p $HOME/results

# =================================================================
# MASTER CONTROL PANEL
# Define exactly which files you want to analyze today!
# (Make sure these 3 files are actually uploaded into your $HOME/inputs folder on Galileo100)
# =================================================================
DATA_CSV="export_sat_alpha_custom.csv"
CONFIG_RULES="Current_rules_sat_alpha.json"
CONFIG_SENSORS="Current_sensors_sat_alpha.yaml"
BATCH_SIZE=10000

# 3. Execute the container, passing all dynamic arguments
echo "Executing the main script inside the container..."

singularity exec \
  --pwd /workspace \
  --bind $HOME/inputs:/workspace/inputs \
  --bind $HOME/results:/workspace/output \
  $IMAGE_NAME \
  python -m src.main \
    --batch_size $BATCH_SIZE \
    --input_path /workspace/inputs/$DATA_CSV \
    --output_path /workspace/output \
    --rules_path /workspace/inputs/$CONFIG_RULES \
    --sensors_path /workspace/inputs/$CONFIG_SENSORS

echo "Job finished."
