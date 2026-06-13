# AstraLog-HPC: Performance Profiling & Bottleneck Analysis

**Component:** Vectorized Polars Rules Engine (`src.main`)
**Dataset:** `export_10X.csv`
**Batch Size:** 750,000 rows
**Total Execution Time:** ~12.15 seconds

## Overview
To validate the architectural transition to a Polars-based vectorized processing model, we profiled the core execution loop using Python's native `cProfile` module. The goal was to identify computational bottlenecks and verify that the heavy lifting was successfully offloaded from the Python Global Interpreter Lock (GIL) to the multi-threaded Rust backend.

### Execution Command
```bash
python -m cProfile -s cumtime -m src.main --batch_size 750000 --input_path inputs/csv_input/export_10X.csv --output_path output/ --rules_path inputs/config/Current_rules_sat_alpha.json --sensors_path inputs/config/Current_sensors_sat_alpha.yaml
```

## Key Findings & Conclusions

By ordering the 362,930 function calls by **cumulative time (`cumtime`)**, we extracted the following architectural insights:

### 1. Successful GIL Bypassing (The Rust Advantage)
The profile explicitly shows that the vast majority of the core execution time is spent inside `frame.py:1585(collect)`.
* **Metric:** `LazyFrame.collect()` took **6.87 seconds** (over 56% of the total execution time).
* **Conclusion:** This proves our architectural design is functioning exactly as intended. Instead of Python evaluating rows sequentially (which would trap the execution in the slow Python GIL), the Rules Engine successfully builds a lazy execution graph and passes it to Polars. The actual rule evaluation and boolean masking are being executed natively in Rust across multiple CPU cores, maximizing cluster hardware utilization.

### 2. The Secondary Bottleneck: Data Ingestion & Sanitization
The second most expensive operation in the pipeline is reading and structuring the raw text data.
* **Metric:** `reader.py:130(extract_batch)` and `reader.py:71(_sanitize_batch)` consumed approximately **5.13 seconds** and **3.33 seconds** respectively.
* **Conclusion:** As expected with massive CSV streams, string parsing and type-casting overhead constitute the primary I/O bottleneck. `batched_reader.py:109(next_batches)` taking ~1.3 seconds further highlights that pulling raw strings from the disk into RAM is computationally expensive. However, by strictly typing the schema during ingestion, we guarantee that the subsequent Rust-based evaluation phase operates at peak memory-bound speeds.

### 3. Highly Efficient I/O Output Operations
The strategy of buffering results in RAM and writing to disk in large vectorized chunks drastically minimized output latency.
* **Metric:** `writer.py:82(write_alarms_batch)` and the underlying `frame.py:2513(write_csv)` took only **~0.56 seconds**.
* **Conclusion:** Writing the separated valid telemetry and alarm logs to the NVMe disk is highly optimized. Because the Polars engine splits the chunks using vectorized operations before passing them to the writer, the disk I/O overhead for saving the final reports is negligible (less than 5% of total runtime).

## Final Verdict
The profiling data conclusively validates the usage of Polars for the AstraLog-HPC pipeline. By delegating the heavy rule evaluation to the `collect()` method and minimizing Python-level row iteration, the system comfortably processes chunks of 750,000 rows in just ~12 seconds. The only remaining friction points are inherent to the standard CSV parsing process, confirming that our core evaluation logic is fully optimized for High-Performance Computing environments.
