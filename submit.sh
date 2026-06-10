#!/bin/bash
# Run this on the login node.
# It fetches the latest .sif built by your CI/CD pipeline from GitLab.

PROJECT_ID="2955" 
TOKEN=$(cat ~/.gitlab_token) # Read the token saved in your home directory / Create a file with your token inside login node and set permissions to 600 for security

echo "Updating container from GitLab Package Registry..."
curl --header "PRIVATE-TOKEN: $TOKEN" \
     "https://gitlab.hpc.cineca.it/api/v4/projects/$PROJECT_ID/packages/generic/astralog-sif/latest/astralog-hpc.sif" \
     --output ~/astralog-hpc.sif

echo "Submitting job to SLURM..."
sbatch job.sh