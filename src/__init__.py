"""
# AstraLog-HPC System Documentation

Welcome to the API Reference for the **AstraLog-HPC** project. 

This system was designed and developed to simulate a high-performance telemetry 
ingestion and monitoring pipeline for the **European Space Agency (ESA)**. 

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
*Developed for the Software Engineering for HPC course (A.Y. 2025-2026).*
"""

__version__ = "1.0.0"
