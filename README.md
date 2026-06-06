# AstraLog-HPC: Full Track Implementation

[![CI/CD Pipeline](https://github.com/DomDegi/DeGiorgioPelorosso/actions/workflows/cicd.yml/badge.svg)](https://github.com/DomDegi/DeGiorgioPelorosso/actions/workflows/cicd.yml)
[![Live Documentation](https://img.shields.io/badge/docs-Live_API_Reference-blue.svg)](https://domdegi.github.io/DeGiorgioPelorosso/)
[![Version](https://img.shields.io/badge/version-1.0.0-success.svg)]()

### **Software Engineering for HPC - A.Y. 2025-2026**

This repository contains the **Full Track** solution for the **AstraLog-HPC** project, developed to respond to a simulated "Call for Tenders" issued by the European Space Agency (ESA).

**Selected track**: Full

---

## AstraLog Control
Here you can access the official documentation hub and web interface for the **AstraLog-HPC** project. 

**[Click here to access AstraLog Control](https://simonereale.github.io/astralog-control/)**

---

## Team Members & Effort

| Name Surname | Person Code | Role / Main Focus | Effort (Hours) |
| :--- | :--- | :--- | :--- |
| **Domenico DeGiorgio** | 10854350 | Software Architect, Rules Parallelization Logic, Pytest, CD Pipeline & SLURM job| 80h |
| **Leonardo Pelorosso** | 10779110 | Use Cases, Domain assumptions, Requirements elicitation, Singularity Container| 80h |

---

## Repository Structure

```text
.
├── .devcontainer/             # VS Code Dev Container configurations
│   ├── devcontainer.json
│   ├── docker-compose.yml
│   └── Dockerfile
├── docker/                    # Production Docker configurations
│   ├── Dockerfile.prod
│   └── Dockerfile.prod.dockerignore
├── docs/                      # Documentation and AstraLog Control site
├── inputs/                    # All configuration and dataset files
│   ├── config/                # YAML and JSON rules/sensors configs
│   └── csv_input/             # Raw CSV telemetry datasets
├── output/                    # Target directory for generated alarms
├── scripts/                   # Benchmarking, profiling, and Bash utilities
├── src/                       # Core Python source code
├── tests/                     # Pytest automated test suite
├── uml/                       # Architecture and sequence diagrams
├── requirements_dev.txt       # Development Python dependencies
├── requirements_prod.txt      # Production Python dependencies
├── job.sh                     # SLURM execution script for Galileo100
├── submit.sh                  # HPC automated submission script
├── run.sh                     # Local testing execution script
├── README.md                  # Project documentation
└── LICENSE                    # MIT License
```

## Software Organization & Architecture 

### Language and Libraries
- **Language:** Python 3.10
- **Libraries:** 
  - `polars` (Rust-backed DataFrame library for massive multithreaded rule evaluation and CSV parsing)
  - `pyyaml` (for parsing sensor configurations)
  - `argparse` (for dynamic Slurm job parameterization)
  - `pytest` (for unit testing in the CI/CD pipeline)

### Architecture & Relation to Phase 1
Our software architecture was designed strictly around the **Strategy** and **Dependency Inversion** patterns established during Phase 1. The core logic (`orchestrator.py`) relies entirely on Abstract Base Classes defined in `interfaces.py` (`ITelemetryReader`, `IRulesEngine`, `IStateMemory`, `IOutputWriter`). 

This interface-driven design allowed us to cleanly separate the physical data handling from the logical rule evaluation:
1. **Reader (`reader.py`):** Utilizes a custom Python list-buffer to bridge Polars' native Rust chunking with the exact sensor-multiple batch sizes required to not split timestamp between batches. It enforces strict type-checking, dropping corrupted rows before they enter the system.
2. **Rules Engine (`rules_engine.py`):** Translates JSON rule configurations into vectorized Polars Eager API queries. It handles complex Stateful and Step-Difference rules by querying the State Memory and applying boolean masking to completely avoid CPU L3-cache exhaustion.
3. **State Memory (`state_memory.py`):** An O(1) in-memory dictionary that persists anomaly streaks and "last known values" across chunk boundaries.
4. **Writer (`writer.py`):** Bypasses slow Python string formatting by utilizing Polars' native `.list.join("|")` at the Rust level to construct the custom ESA nominal formats before appending to disk.

### Simplifications and variations
**Batch Size Auto-Alignment:** The `batch_size`, given as a CLI argument, gets automatically sanitized and adjusted to the nearest multiple of the number of active sensors in the configuration. This ensures that a single timestamp is never mathematically split across two different evaluation batches.

### Distribution and parallelization approach
*(Note: As a group of two students, we utilized the CSV track. However, our pipeline is heavily parallelized for HPC environments).*

To achieve maximum throughput (processing ~850,000 rows/second), we migrated from a single-threaded Pandas approach to a **Polars / Rust multi-threaded architecture**. 
By chunking the CSV into batches of ~1.6 million rows, we effectively feed the Polars Rayon thread pool with enough data to utilize at full 32-core SLURM compute node, preventing thread starvation while keeping the overall RAM footprint highly constrained. Mathematical operations like `.diff()` and `.cum_sum()` are executed completely in C/Rust, avoiding the Python Global Interpreter Lock (GIL).

### Usage of AI 
AI assistants (Gemini) were used primarily as a technical consultant to:
- General deubg.
- Understand and debug containerization concepts (Docker to Singularity conversion).
- Transport our original Pandas implementetion to Polars.
- Formulate the CI/CD pipeline syntax for GitHub Actions.
- Profile C-level execution times to identify and eliminate $O(N^2)$ memory-copying bottlenecks during the Pandas-to-Polars migration.
- Configure SLURM scripts to avoid NFS login-node throttling by mapping container I/O directly to high-speed NVMe cluster scratch space (`$WORK`).
- Generate the pdoc comments and integrate them in the code after reviewing them.
- Add the deployment of the pdoc as github pages to the ci/cd pipeline.
- Fix the action deploying the pdocs and also the link to the UML images in the __init__.py comments (done with github copilot).

---

## Testing & Rationale

We implemented our test suite using `pytest`. The tests are designed to run automatically during the CI/CD pipeline to ensure code integrity before building the container.

- **Isolation via Interfaces:** Because our architecture relies on interfaces, we were able to write unit tests for the `RulesEngine` without needing actual CSV files or I/O operations. We mocked the `IStateMemory` and passed raw DataFrames directly into the engine to verify edge cases (e.g., streak continuity across batches, complex AND/OR correlations).
- **Sanitization Testing:** Tests ensure the `CSVTelemetryReader` correctly identifies and drops malformed data according to Polars' strict schema checking without crashing the pipeline.
- **Snapshots:** End-to-end regression tests verify that the output strings exactly match legacy baseline outputs regardless of internal hardware threading order.

To run the tests locally:
```bash
python3 -m pytest tests/
```

---

## Pipeline & DevOps Workflow

Our project utilizes a modern, zero-touch CI/CD pipeline built on **GitHub Actions**.

1. **Continuous Integration (CI):** Upon every push to the `main` branch, the pipeline spins up a virtual environment, installs dependencies, and runs the `pytest` suite (23 tests).
2. **Continuous Deployment (CD):** If the tests pass, the pipeline automatically builds a production Docker image using `Dockerfile.prod` and pushes it to the GitHub Container Registry (GHCR).
3. **HPC Execution:** On the CINECA Galileo100 supercomputer, our `job.sh` SLURM script utilizes **Singularity (Apptainer)** to execute the container. 

### Cluster Operating Procedure (CINECA G100)

To achieve maximum I/O throughput, our `job.sh` script automatically creates an isolated, job-specific scratch directory on the cluster's high-speed `$WORK` filesystem, moving data off the slow network-mounted `$HOME` directory before executing the container.

**1. Upload Inputs:**
Run these commands from your local terminal to push files to CINECA:
```bash
ssh username@login.g100.cineca.it "mkdir -p ~/inputs ~/results"
scp config/Current_sensors_sat_alpha.yaml username@login.g100.cineca.it:~/inputs/
scp config/Current_rules_sat_alpha.json username@login.g100.cineca.it:~/inputs/
scp csv_input/export_100X.csv username@login.g100.cineca.it:~/inputs/
scp job.sh submit.sh username@login.g100.cineca.it:~/
```

**2. Prepare the Container Image:**
Compute nodes lack internet access, so the image must be downloaded on the login node first to generate the `.sif` file. You can do this in two ways:

*Option A: Automated Submit Script*
Make the uploaded `submit.sh` script executable and run it. It will automatically download the image from GHCR and submit the Slurm job for you:
```bash
ssh username@login.g100.cineca.it
chmod +x submit.sh
./submit.sh
```

*Option B: Manual Pull*
If you prefer to submit the job manually, run the singularity pull command on the login node first:
```bash
ssh username@login.g100.cineca.it
singularity pull astralog-hpc.sif docker://ghcr.io/domdegi/astralog-hpc:latest
```

**3. Execute the Job (If using Option B):**
On the cluster, submit the job to the dedicated `usr_prod` compute partition (32 Cores, 64GB RAM):
```bash
sbatch job.sh
```

**4. Monitor and Download Results:**
Check the live terminal output via the generated log:
```bash
cat astralog_run_<JOB_ID>.log
```
Once the job finishes, pull the generated data back to your local machine:
```bash
scp -o StrictHostKeyChecking=no -r username@login.g100.cineca.it:~/astralog_results_<JOB_ID> ./
```

---

## License

This project is licensed under the **MIT License**. See the `LICENSE` file for more details.
