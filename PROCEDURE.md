# AstroLog-HPC Execution Guide

This guide details how to run the AstroLog containerized application on an HPC cluster using Apptainer (formerly Singularity). 

The recommended approach is to pull the pre-built container directly from the GitHub Container Registry (GHCR). A manual build and transfer approach is also provided for completeness.

## Prerequisites

Before executing the job, you must log into the HPC login node via SSH and navigate to your designated work directory:

```bash
ssh your_username@login.g100.cineca.it
cd /g100/work/YOUR_ACCOUNT_NAME
```

---

## Method 1: Pulling from GitHub Container Registry (Recommended)

This is the most efficient and robust method. Our CI/CD pipeline automatically builds and hosts the Docker image on GHCR. Apptainer can pull this image and convert it to a native `.sif` file directly on the cluster.
```bash
# 1. Load the Apptainer module
module load apptainer

# 2. Pull and build the container from GHCR
apptainer pull astralog-hpc.sif docker://ghcr.io/domdegi/astralog-hpc:latest
```

---

## Method 2: Manual Build and Transfer

If you need to build the container definition locally and manually transfer it to the cluster, follow these steps from your local machine.
```bash
# 1. Build the container locally using the Singularity definition file
apptainer build astralog-hpc.sif Singularity.def

# 2. Transfer the .sif file to the cluster
scp astralog-hpc.sif your_username@login.g100.cineca.it:/g100/work/YOUR_ACCOUNT_NAME/
```

---

## Executing the Slurm Job

Once the `astralog-hpc.sif` file is present in your workspace (via Method 1 or Method 2), you can submit the job.

1. Ensure the `job.sh` script is located in your workspace. If not, transfer it:
   ```bash
   scp job.sh your_username@login.g100.cineca.it:/g100/work/YOUR_ACCOUNT_NAME/
   ```

2. Submit the script to the Slurm workload manager:
   ```bash
   sbatch job.sh
   ```

3. You can monitor your job's status using:
   ```bash
   squeue -u your_username
   ```

## Retrieving Results

Once the job has completed, download the output files to your local machine for review or version control. Execute the following commands from a local terminal:
```bash
scp your_username@login.g100.cineca.it:/g100/work/YOUR_ACCOUNT_NAME/astralog_output.txt .
scp your_username@login.g100.cineca.it:/g100/work/YOUR_ACCOUNT_NAME/astralog_error.txt .
```
