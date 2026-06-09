#!/bin/bash

# Configuration
IMAGE_NAME="astralog-hpc.sif"
IMAGE_URL="docker://ghcr.io/domdegi/astralog-hpc:latest"

echo "Checking for container updates from GHCR..."

# Pull the image (the --force flag ensures it overwrites the old one with the latest push)
singularity pull --force $IMAGE_NAME $IMAGE_URL

echo "Container updated successfully."

echo "Submitting job to Galileo100 SLURM queue..."

# Submit the SLURM job
sbatch job.sh

# Display the user's current queue status
echo "Current queue status:"
squeue -u $USER