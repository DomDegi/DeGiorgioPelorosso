#!/bin/bash

# 1. This script runs on the Login Node, so it has internet!
IMAGE_NAME="astralog-hpc.sif"
IMAGE_URL="docker://ghcr.io/domdegi/astralog-hpc:latest"

echo "Checking for container updates..."

# Pull the image (the --force flag ensures it overwrites the old one with your latest GitHub push)
singularity pull --force $IMAGE_NAME $IMAGE_URL

echo "Container updated successfully!"

# 2. Now that the file is safely on the cluster, submit the job to the Compute Node
echo "Submitting job to Galileo100..."
sbatch job.sh
