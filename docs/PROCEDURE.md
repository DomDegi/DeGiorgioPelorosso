# 🚀 AstraLog-HPC: Cluster Operating Procedure

This document outlines the "Gold Standard" HPC workflow used for this project. The architecture strictly separates the containerized code from the input data.

Because CINECA Galileo100 compute nodes do not have internet access, we utilize a wrapper script (`submit.sh`) on the login node to pull the container from the GitHub Container Registry before submitting the job to the compute nodes via SLURM.

### PHASE 1: UPLOAD DATA & CONFIGURATIONS
Whenever you want to run a new experiment, you must upload your datasets and configuration files to the cluster. Run these commands from your **LOCAL** terminal:

```bash
# 1. Create the required directories on the cluster
ssh <username>@login.g100.cineca.it "mkdir -p ~/inputs ~/results"

# 2. Upload Configurations (YAML/JSON)
scp inputs/config/Current_sensors_sat_alpha.yaml <username>@login.g100.cineca.it:~/inputs/
scp inputs/config/Current_rules_sat_alpha.json <username>@login.g100.cineca.it:~/inputs/

# 3. Upload Telemetry Data (CSV)
scp inputs/csv_input/export_sat_alpha_custom_no_corruption.csv <username>@login.g100.cineca.it:~/inputs/

# 4. Upload the Job & Submit Scripts
scp job.sh submit.sh <username>@login.g100.cineca.it:~/
```

### PHASE 2: EXECUTE THE JOB
SSH into the CINECA login node: `ssh username@login.g100.cineca.it`

If you want to change the target CSV or config files, simply edit the variables at the top of `job.sh` using `nano job.sh`.

1. **Make the wrapper script executable (First time only):**
   ```bash
   chmod +x submit.sh
   ```

2. **Execute the wrapper script:**
   This will download the latest container from GHCR and automatically submit the `job.sh` script to the SLURM queue.
   ```bash
   ./submit.sh
   ```
3. **Monitor the job:**
   ```bash
   squeue -u <username>

### PHASE 3: DOWNLOAD RESULTS
Once the job finishes, pull the generated data back to your local machine. Run this from your **LOCAL** terminal:

```bash
# Download the entire results folder (use StrictHostKeyChecking=no to bypass load balancer SSH warnings)
scp -o StrictHostKeyChecking=no -r username@login.g100.cineca.it:~/results ./

# Download the execution logs
scp -o StrictHostKeyChecking=no username@login.g100.cineca.it:~/astralog_output.txt ./
scp -o StrictHostKeyChecking=no username@login.g100.cineca.it:~/astralog_error.txt ./
```
