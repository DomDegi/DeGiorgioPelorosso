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

# Load Singularity
module load singularity

# Execute the container! 
# We tell python to run the script that is permanently baked into the container's /workspace
singularity exec --pwd /workspace --bind $HOME/results:/workspace/output astralog-hpc.sif python -m src.main --batch_size 10000

echo "Job finished."
