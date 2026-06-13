"""
AstraLog-HPC Automated Test Suite.

-> **[Click here to return to the Main API Reference (Home)](index.html)**

---

This module contains the comprehensive automated testing environment for the system.
The suite is designed utilizing `pytest` and relies heavily on the **Dependency Injection** pattern to isolate components for pure logic verification without requiring heavy Disk I/O.

**Test Coverage:**
-> **[Click here to view the live Codecov Coverage Dashboard](https://app.codecov.io/github/DomDegi/DeGiorgioPelorosso/)**

### Submodules:
* **`test_rules_engine`**: Unit tests verifying single, stateful, and correlation math.
* **`test_orchestrator`**: Unit tests verifying OOM caps and batch-alignment safety math.
* **`test_general`**: End-to-End integration tests utilizing isolated temporary files.
* **`test_reader` / `test_writer` / `test_memory`**: Component-specific structural validations.
"""
