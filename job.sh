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

# Load Singularity module (Galileo100 supports this alias for Apptainer)
module load singularity

# Define the image name and the GHCR registry URL
IMAGE_NAME="astralog-hpc.sif"
# IMPORTANT: Replace YOUR_GITHUB_USERNAME with your actual lowercase GitHub username
IMAGE_URL="docker://ghcr.io/YOUR_GITHUB_USERNAME/astralog-hpc:latest"

# 1. SETUP: Check if the image exists, pull it if it doesn't
if [ ! -f "$IMAGE_NAME" ]; then
    echo "Image '$IMAGE_NAME' not found in the current directory."
    echo "Pulling from $IMAGE_URL..."
    singularity pull $IMAGE_NAME $IMAGE_URL
else
    echo "Image '$IMAGE_NAME' already exists. Skipping download."
fi

# 2. SETUP: Ensure the host output directory exists before binding it
# If the directory doesn't exist, Singularity will throw a mount error
mkdir -p $HOME/results

# 3. EXECUTE: Run the container
# We tell python to run the script that is permanently baked into the container's /workspace
echo "Executing the main script inside the container..."
singularity exec --pwd /workspace --bind $HOME/results:/workspace/output $IMAGE_NAME python -m src.main --batch_size 10000

echo "Job finished."