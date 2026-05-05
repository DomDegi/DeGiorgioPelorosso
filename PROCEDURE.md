# ASTRALOG-HPC CLUSTER OPERATING PROCEDURE

The container is static and clean. You only rebuild the container when Python code changes. For daily tests, you only swap the input files.

### PHASE 1: UPDATE CODE (Only when modifying .py files)
1. [LOCAL] Edit `rules_engine.py`.
2. [LOCAL] Commit and push to GitHub.
3. [GITHUB] Wait for the CI/CD Action to finish building the Docker image.
4. [GALILEO100] Delete the old container so the job script downloads the fresh one:
   rm ~/astralog-hpc.sif

---

### PHASE 2: UPLOAD INPUTS (Every time you run a new experiment)
Run these commands from your LOCAL terminal to push files to CINECA:

# 1. Create the inputs folder if it doesn't exist
ssh username@login.g100.cineca.it "mkdir -p ~/inputs ~/results"

# 2. Upload Configs (YAML/JSON)
scp config/Current_sensors_sat_alpha.yaml username@login.g100.cineca.it:~/inputs/
scp config/Current_rules_sat_alpha.json username@login.g100.cineca.it:~/inputs/

# 3. Upload Telemetry Data (CSV)
scp csv_input/export_sat_alpha_custom.csv username@login.g100.cineca.it:~/inputs/

# 4. Upload the Master Job Script
scp job.sh username@login.g100.cineca.it:~/

---

### PHASE 3: EXECUTE THE JOB
If you want to change the target CSV or config files without uploading a new job.sh, simply edit the variables at the top of `job.sh` using `nano job.sh`.

1. [CINECA] Submit the job to the Slurm workload manager:
   sbatch job.sh

2. [CINECA] Check the status of your job:
   squeue -u username

3. [CINECA] View the live terminal output:
   cat astralog_output.txt
   cat astralog_error.txt

---

### PHASE 4: DOWNLOAD RESULTS
Once the job finishes, pull the generated data back to your local machine.
Run this from your LOCAL terminal:

# Download the entire results folder (use StrictHostKeyChecking=no to bypass load balancer warnings)
scp -o StrictHostKeyChecking=no -r username@login.g100.cineca.it:~/results ./

# (Optional) Download the logs
scp -o StrictHostKeyChecking=no username@login.g100.cineca.it:~/astralog_output.txt ./
scp -o StrictHostKeyChecking=no username@login.g100.cineca.it:~/astralog_error.txt ./
