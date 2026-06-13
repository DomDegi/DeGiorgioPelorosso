# Performance Profiling: The Pandas Bottleneck

**Date:** May 7, 2026
**Environment:** CINECA Galileo100 / DevContainer (16 Cores, 32GB RAM)
**Task:** Process a 5,000,000-row batch of CSV telemetry data.
**Architectural Decision:** Migrate core data processing from `pandas` to `polars`.

## 1. The Profiling Command
To diagnose a severe performance bottleneck during the HPC stress test, the following `cProfile` command was executed to trace the Python call stack:

```bash
python -m cProfile -s cumtime -m src.main \
  --batch_size 5000000 \
  --input_path csv_input/export_100X.csv \
  --output_path output/ \
  --rules_path config/Current_rules_sat_alpha.json \
  --sensors_path config/Current_sensors_sat_alpha.yaml
```

## 2. The Execution Summary
The total execution time for a single batch of 5 million rows was **~34.5 minutes (2071 seconds)**.

```text
2026-05-07 07:26:07,663 - src.reader - INFO - CSVTelemetryReader initialized
2026-05-07 08:00:38,694 - AstraLog-Main - INFO - Total Execution Time: 2071.1301 seconds
         600937789 function calls (600885965 primitive calls) in 2072.376 seconds
```

## 3. The `cProfile` Trace (The Smoking Gun)
Sorting the trace by cumulative time (`cumtime`) revealed exactly where the CPU spent its time. Over **92% of the execution time (1919 seconds)** was spent inside `reader.py`, specifically running Python `lambda` functions and type-checking.

```text
   Ordered by: cumulative time
   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
       22    0.004    0.000 1919.416   87.246 reader.py:123(extract_batch)
       21    3.338    0.159 1872.099   89.148 reader.py:56(_sanitize_batch)
       84    0.002    0.000 1807.977   21.524 base.py:891(_map_values)
       84  501.366    5.969 1807.975   21.524 algorithms.py:1667(map_array)
       63    0.001    0.000 1804.712   28.646 series.py:4789(apply)
 99755499  291.532    0.000  435.291    0.000 reader.py:89(<lambda>)
 99755499  290.691    0.000  434.010    0.000 reader.py:88(<lambda>)
 99755499  290.739    0.000  433.982    0.000 reader.py:87(<lambda>)
299753170  431.234    0.000  431.763    0.000 {built-in method builtins.isinstance}
       21    1.232    0.059   84.043    4.002 rules_engine.py:188(evaluate_rules)
       21    0.000    0.000   64.041    3.050 writer.py:80(write_alarms_batch)
```

## 4. Engineering Conclusion & Action Plan
The trace mathematically proves that **the bottleneck is not the I/O read/write phase, nor is it the business logic (`rules_engine.py` took only 84s).** The bottleneck is the data sanitization phase inside `reader.py`. By using Pandas `.apply(lambda x: ...)` to clean malformed data, Pandas was forced to abandon its vectorized C-backend. It extracted data into standard Python space, running `isinstance()` **299 million times** in a slow, single-threaded scalar loop.

**Action:** To meet the ESA High-Performance Computing requirements while keeping the input/output as `.csv`, we must replace `pandas` with `polars`. Polars uses strict schema enforcement at the Rust/C level during the read phase, completely eliminating the need for Python `lambda` sanitization loops and saturating all available CPU cores.
