# 🚀 AstraLog-HPC: Full Track Implementation
### **Software Engineering for HPC - A.Y. 2025-2026**

This repository contains the **Full Track** solution for the **AstraLog-HPC** project, developed to respond to a simulated "Call for Tenders" issued by the European Space Agency (ESA).

**Selected track**: Full

---

## 👥 Team Members & Effort

| Name Surname | Person Code | Role / Main Focus | Effort (Hours) |
| :--- | :--- | :--- | :--- |
| **Domenico DeGiorgio** | 10854350 | Software Architect, Rules Parallelization Logic, Pytest, CD Pipeline & SLURM job| 80h |
| **Leonardo Pelorosso** | 10779110 | Use Cases, Domain assumptions, Requirements elicitation, Singularity Container| 260h |

---

## 📁 Repository Structure

```text
.
├── config/                    # Contains YAML and JSON configuration files
│   ├── Current_rules_sat_alpha.json
│   └── Current_sensors_sat_alpha.yaml
├── csv_input/                 # Input datasets for testing
├── src/                       # Source code directory
│   ├── interfaces.py          # Abstract Base Classes defining system architecture
│   ├── main.py                # Entry point handling argument parsing
│   ├── orchestrator.py        # Main execution loop and component wiring
│   ├── reader.py              # CSV ingestion and data sanitization
│   ├── rules_engine.py        # Core logic evaluating Simple, Step, Stateful, and Correlation rules
│   ├── state_memory.py        # In-memory dictionary for cross-batch state tracking
│   └── writer.py              # I/O handler for exporting valid data and alarms
├── .github/workflows/         # CI/CD Pipeline configuration
│   └── cicd.yml               # Automated Pytest and Docker image build/push
├── job.sh                     # Slurm script for CINECA Galileo100 execution
├── Dockerfile.prod            # Production blueprint for containerization
├── requirements_prod.txt      # Production Python dependencies
├── requirements_dev.txt       # Development dependencies (including Pytest)
└── tests/                     # Automated test suite
```

---

## 🛠️ Software Organization & Architecture 

### Language and Libraries
- **Language:** Python 3.10
- **Libraries:** 
  - `pandas` (for high-performance, vectorized rule evaluation and chunked file reading)
  - `pyyaml` (for parsing sensor configurations)
  - `argparse` (for dynamic Slurm job parameterization)
  - `pytest` (for unit testing in the CI/CD pipeline)

### Architecture & Relation to Phase 1
Our software architecture was designed strictly around the **Strategy** and **Dependency Inversion** patterns established during Phase 1. The core logic (`orchestrator.py`) relies entirely on Abstract Base Classes defined in `interfaces.py` (`ITelemetryReader`, `IRulesEngine`, `IStateMemory`, `IOutputWriter`). 

This interface-driven design allowed us to cleanly separate the physical data handling from the logical rule evaluation:
1. **Reader (`reader.py`):** Utilizes Pandas chunking to read massive CSV files in RAM-safe batches. It enforces strict type-checking, dropping corrupted rows before they enter the system.
2. **Rules Engine (`rules_engine.py`):** Translates JSON rule configurations into vectorized Pandas operations. It handles complex Stateful and Step-Difference rules by querying the State Memory.
3. **State Memory (`state_memory.py`):** An O(1) in-memory dictionary that persists anomaly streaks and "last known values" across chunk boundaries.
4. **Writer (`writer.py`):** Formats the separated nominal and anomalous data according to ESA specifications and appends them to disk.

### Simplifications and variations (if any)
The batch_size, given as an argument, gets changed to the nearest multiple of the number of sensors in the configurations, so that the batches are all the same size.


### Usage of AI (if any)
AI assistants (Gemini) were used primarily as a technical consultant to:
- Understand and debug containerization concepts (Docker to Singularity conversion).
- Formulate the CI/CD pipeline syntax for GitHub Actions.
- Optimize Pandas vectorized operations for evaluating complex stateful rules.

---

## 🧪 Testing & Rationale

We implemented our test suite using `pytest`. The tests are designed to run automatically during the CI/CD pipeline to ensure code integrity before building the container.

- **Isolation via Interfaces:** Because our architecture relies on interfaces, we were able to write unit tests for the `RulesEngine` without needing actual CSV files or I/O operations. We mocked the `IStateMemory` and passed raw Pandas DataFrames directly into the engine to verify edge cases (e.g., streak continuity across batches, complex AND/OR correlations).
- **Sanitization Testing:** Tests were written to ensure the `CSVTelemetryReader` correctly identifies and drops malformed data (e.g., strings in numerical columns) without crashing the pipeline.

To run the tests locally:
```bash
pytest # in the repo root
```

---

## 🚀 Pipeline & DevOps Workflow

Our project utilizes a modern, zero-touch CI/CD pipeline built on **GitHub Actions**.

1. **Continuous Integration (CI):** Upon every push to the `main` branch, the pipeline spins up a virtual environment, installs dependencies, and runs the `pytest` suite.
2. **Continuous Deployment (CD):** If the tests pass, the pipeline automatically builds a production Docker image using `Dockerfile.prod`.
3. **Registry Publication:** The image is pushed to the GitHub Container Registry (GHCR).
4. **HPC Execution:** On the CINECA Galileo100 supercomputer, our `job.sh` Slurm script utilizes **Singularity (Apptainer)** to pull the latest image directly from GHCR (`singularity pull docker://ghcr.io/...`). The container is completely stateless; the input datasets and configurations are injected via bind mounts (`--bind`) at runtime.

---

## 🖥️ Cluster Operating Procedure

Our architecture physically separates the containerized code from the input data. You only rebuild the container when the underlying Python logic changes. For daily tests, you only swap the input files.

### PHASE 1: UPDATE CODE (Only when modifying .py files)
1. **[LOCAL]** Edit `main.py`, `orchestrator.py`, or `rules_engine.py`.
2. **[LOCAL]** Commit and push to GitHub.
3. **[GITHUB]** Wait for the CI/CD Action to finish building the Docker image.
4. **[CINECA]** Delete the old container so the job script downloads the fresh one:
   ```bash
   rm ~/astralog-hpc.sif
   
```

### PHASE 2: UPLOAD INPUTS (Every time you run a new experiment)
Run these commands from your **LOCAL** terminal to push files to CINECA:

```bash
# 1. Create the inputs folder if it doesn't exist
ssh username@login.g100.cineca.it "mkdir -p ~/inputs ~/results"

# 2. Upload Configs (YAML/JSON)
scp config/Current_sensors_sat_alpha.yaml username@login.g100.cineca.it:~/inputs/
scp config/Current_rules_sat_alpha.json username@login.g100.cineca.it:~/inputs/

# 3. Upload Telemetry Data (CSV)
scp csv_input/export_sat_alpha_custom.csv username@login.g100.cineca.it:~/inputs/

# 4. Upload the Master Job Script
scp job.sh username@login.g100.cineca.it:~/
```

### PHASE 3: EXECUTE THE JOB
If you want to change the target CSV or config files without uploading a new `job.sh`, simply edit the variables at the top of `job.sh` using `nano job.sh` on the cluster.

1. **[CINECA]** Submit the job to the Slurm workload manager:
   ```bash
   sbatch job.sh
   
```
2. **[CINECA]** Check the status of your job:
   ```bash
   squeue -u username
   ```
3. **[CINECA]** View the live terminal output:
   ```bash
   cat astralog_output.txt
   cat astralog_error.txt
   
```

### PHASE 4: DOWNLOAD RESULTS
Once the job finishes, pull the generated data back to your local machine. Run this from your **LOCAL** terminal:

```bash
# Download the entire results folder (use StrictHostKeyChecking=no to bypass load balancer warnings)
scp -o StrictHostKeyChecking=no -r username@login.g100.cineca.it:~/results ./

# (Optional) Download the logs
scp -o StrictHostKeyChecking=no username@login.g100.cineca.it:~/astralog_output.txt ./
scp -o StrictHostKeyChecking=no username@login.g100.cineca.it:~/astralog_error.txt ./
```

---

## 📄 License
This project is licensed under the **MIT License**. See the `LICENSE` file for more details.