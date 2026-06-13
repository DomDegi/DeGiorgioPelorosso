"""
# AstraLog-HPC System Documentation

Welcome to the API Reference for the **AstraLog-HPC** project.

This system was designed and developed to simulate a high-performance telemetry
ingestion and monitoring pipeline for the **European Space Agency (ESA)**.

-> **[Click here to download the Phase 1 Design Document (RASD PDF)](AstraLog_RASD.pdf)**

---

### System Architecture (Component View)
The system is built on a highly modular and encapsulated architecture, designed
specifically to be robust and highly scalable in a multithreaded environment.

![Component Diagram](https://raw.githubusercontent.com/DomDegi/DeGiorgioPelorosso/main/uml/component_diagram.png)

---

### Object-Oriented Design (Class View)
To ensure maintainability and testability, the Orchestrator is completely decoupled
from the concrete implementations via Abstract Base Classes (Interfaces).

![Class Diagram](https://raw.githubusercontent.com/DomDegi/DeGiorgioPelorosso/main/uml/class_diagram.png)

---

### HPC Performance & Scalability

#### 1. Batch Size Optimization (Galileo100)
To maximize hardware utilization on the CINECA Galileo100 compute nodes (32 CPUs, 64GB RAM were used), the
system underwent strict empirical profiling. The resulting "bathtub curve" identified the
optimal operational batch size (200,000 rows), perfectly balancing the computational chunking
overhead against raw memory capacity.

<img src="https://raw.githubusercontent.com/DomDegi/DeGiorgioPelorosso/main/docs/benchmark_plot_galileo100_32CPU_64GB.png" width="800">

#### 2. Linear Scalability
Using the empirically optimized batch size, the pipeline exhibits near-perfect linear scalability
when processing massive telemetry streams. The vectorized
Polars Rules Engine effectively bypasses the Python Global Interpreter Lock (GIL), distributing
the workload natively across all available Rust threads.

<img src="https://raw.githubusercontent.com/DomDegi/DeGiorgioPelorosso/main/docs/scalability_plot_optimal_batch_200k.png" width="800">

---

### Navigation
Use the **sidebar on the left** to explore the individual modules, abstract interfaces,
and concrete classes that power the system:
* **`reader`**: Safely ingests physical chunks of data and sanitizes structural corruption.
* **`rules_engine`**: Evaluates telemetry using vectorized, high-speed Polars expressions.
* **`state_memory`**: A single-node dictionary tracker ensuring continuity across batches.
* **`writer`**: Exports data matching strict ESA string formatting requirements.

---

### System Safety & Testing
AstraLog-HPC is built with absolute reliability in mind. We have implemented a comprehensive
automated test suite using `pytest` and **Dependency Injection** to verify Out-Of-Memory (OOM)
protections, safe chunk alignment, and mathematical correlation logic.

-> **[Click here to view the Automated Test Suite Documentation](tests.html)**

---

*Version: 1.2.0

*Developed for the Software Engineering for HPC course (A.Y. 2025-2026).*
"""

__version__ = "1.2.0"
