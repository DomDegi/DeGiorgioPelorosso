## 1. Core Architecture & Interfaces (`interfaces.py`)

The foundational architecture of the AstraLog-HPC project is built upon the **Dependency Inversion Principle** and the **Strategy Pattern**. By defining a set of strictly typed Abstract Base Classes (ABCs), the system cleanly decouples the high-level orchestration loop from the low-level physical implementations of data processing, state management, and I/O operations.

This approach guarantees high modularity, allowing individual components (such as swapping Pandas for Polars, or CSVs for a SQL database) to be modified or upgraded without triggering cascading rewrites throughout the system. Furthermore, it makes unit testing highly effective by allowing dependencies to be easily mocked via `pytest`.

### 1.1 Domain Terminology
To maintain ubiquitous language across the documentation and codebase, the following definitions are strictly enforced:
* **Batch:** A logical unit of work processed in a single loop iteration by the application. It represents a discrete step in time.
* **Chunk:** A physical block of memory or data read from/written to the disk by libraries (e.g., Polars). During execution, a physical chunk is ingested and transformed into a logical batch.
* **Telemetry:** The domain-specific aerospace term representing the actual data payload (e.g., sensor readings like `VOLT-MAIN`).

### 1.2 `ITelemetryReader` (Data Ingestion)
This interface acts as the gateway into the system.
* **Design Rationale:** It completely abstracts the source of the incoming data. The system does not need to know if it is reading from a local CSV, an S3 bucket, or a live data stream.
* **Core Contract:** The `extract_batch(batch_size)` method defines a strict boundary where physical data chunks are ingested, sanitized, and yielded to the orchestrator as a clean, standardized Polars `DataFrame`. The `batch_size` parameter acts as a strict memory-governor to prevent RAM exhaustion on HPC nodes.

### 1.3 `IRulesEngine` (Business Logic)
This is the mathematical heart of the application.
* **Design Rationale:** Rule evaluation requires heavy vectorization and complex threshold logic. By confining this behind an interface, the orchestrator remains entirely agnostic to *how* the rules are evaluated.
* **Core Contract:** The `evaluate_rules(telemetry_batch)` method takes a raw telemetry batch and applies the system's ruleset. It enforces a strict output format: returning a Tuple containing two separate DataFrames—one for perfectly valid, nominal telemetry `[0]`, and one strictly containing threshold breaches and anomalies `[1]`.

### 1.4 `IStateMemory` (Cross-Batch Persistence)
This component solves the critical problem of analyzing time-series data that is artificially cut into memory chunks.
* **Design Rationale:** Many ESA rules are context-dependent (e.g., *Stateful* rules checking for 5 consecutive errors, or *Step* rules comparing the current value to the previous one). Because HPC processing requires chunking data, a streak might start in "Batch A" and finish in "Batch B". This interface obscures how the system "remembers" the past.
* **Core Contracts:**
  * **Stateful Tracking:** `get_current_count` and `set_consecutive_count` allow the rules engine to pull the active anomaly streak of a specific sensor from the previous batch, and overwrite it with the final streak at the end of the current batch.
  * **Step Difference Tracking:** `get_last_value` and `set_last_value` provide the exact float value of a sensor at the final timestamp of a batch, providing the mathematical anchor required to calculate differentials ($T_n - T_{n-1}$) at the start of the next batch.

### 1.5 `IOutputWriter` (Data Exportation)
This interface handles the final physical manifestation of the processed data.
* **Design Rationale:** Similar to the reader, it prevents the orchestrator from being tied to specific output paths, database schemas, or string-formatting logic.
* **Core Contracts:** It provides two distinct pipelines: `write_valid_batch` and `write_alarms_batch`. This enforces the architectural requirement that nominal data and anomalies are treated as entirely separate data streams once evaluated, ready to be appended to their respective physical storage locations.

## 2. Core Business Logic: The Rules Engine (`rules_engine.py`)

The `PolarsRulesEngine` is the computational heart of the AstraLog-HPC system. Moving away from single-threaded, Python-bound execution (e.g., standard Pandas or native loops), this engine leverages **Polars**, a Rust-backed DataFrame library.

This design choice allows the engine to translate complex JSON business rules into Polars Expressions (`pl.Expr`), which are then executed asynchronously across the HPC node's entire CPU core topology, bypassing the Python Global Interpreter Lock (GIL) entirely.

### 2.1 Rule Ingestion & AST Translation
Upon initialization, the engine reads the configuration JSON, sanitizes rule priorities (`HIGH`, `MEDIUM`, `LOW`), and sorts them. Higher priority rules are sorted first to ensure deterministic sorting in the final output phase.
The internal method `_get_op_expr` acts as an Abstract Syntax Tree (AST) translator, converting string-based JSON operators (e.g., `">="`) into vectorized Polars expressions.

### 2.2 Phase 1: Vectorized Base Rules & The "HPC Bridge"
Phase 1 evaluates `simple`, `step_difference`, and `stateful` rules. Because the dataset is physically split into multiple chunks to prevent RAM overflow, the engine employs specialized "HPC Bridge" techniques to maintain logical continuity across physical chunk boundaries.

* **The Global Indexing Strategy (`orig_idx`):**
  Before any filtering occurs, the engine attaches a strict row index (`batch_with_idx = batch.with_row_count("orig_idx")`). When sensors are isolated and evaluated, this ensures that boolean masks can be mapped back to the exact global rows without index-misalignment bugs (e.g., accidentally flagging Sensor 1 for an anomaly caused by Sensor 2).

* **Step-Difference Evaluation (`diff()` patching):**
  To calculate $T_n - T_{n-1}$, the engine uses the natively vectorized `.diff()` function. However, the very first row of a chunk will always yield a `null` differential. The engine bridges the memory gap by querying the `IStateMemory` for the final value of the previous chunk, and cleanly patches only the `null` using `.fill_null(pl.col('value') - last_val)`.

* **Stateful Evaluation (Avoiding $O(N^2)$ complexity):**
  Calculating consecutive streaks (e.g., "5 consecutive errors") using standard iteration destroys L3-cache efficiency. Instead, the engine groups contiguous anomalies into mathematical "blocks" using `(~op_mask).cast(pl.Int32).cum_sum()`. It then calculates the streak strictly at the C/Rust level using a windowed cumulative sum: `.cum_sum().over('block')`.
  If the very first measurement of a new chunk is a breach, it queries `IStateMemory` and adds the inherited streak from the previous chunk to the current calculation.

### 2.3 Phase 2: Correlation Rules
Correlation rules (evaluating multiple sensors simultaneously using `AND`/`OR` logic) are executed *after* Phase 1, treating the results of the base rules as their input variables.

* By storing the boolean masks generated in Phase 1 (`rule_masks` dict), the engine performs extremely fast timestamp-based intersections (`AND`) or unions (`OR`) without recalculating the underlying mathematical thresholds.
* To comply with ESA output requirements, the values of the triggering sensors are concatenated sequentially (e.g., `val1,val2`) ensuring the exact chronological order of the parent sensors defined in the JSON array.

### 2.4 Phase 3: Strict Separation & Sorting
The core interface contract requires outputting two entirely separate DataFrames: one for nominal data, and one for alarms.

* **Isolation via `any_horizontal`:** The engine horizontally scans the dictionary of evaluated masks. Any row matching `True` across *any* evaluated rule is flagged as anomalous. This binary mask guarantees strict separation between `valid_telemetry` and `alarm_telemetry`.
* **Deterministic Sorting:** The anomalies are grouped and sorted to ensure that logs are perfectly reproducible regardless of underlying multithreading execution order. The output is strictly ordered by:
  1. `timestamp` (Ascending)
  2. `priority` (Descending: HIGH -> MEDIUM -> LOW)
  3. `rule_id` (Ascending)
  4. `sensor_id` (Ascending)

## 3. Cross-Batch Memory Management: State Memory (`state_memory.py`)

The `DictStateMemory` class provides the concrete implementation for the `IStateMemory` interface. Because the HPC orchestrator artificially slices continuous time-series data into discrete, memory-safe physical chunks, this module acts as the "bridge" that allows the system to remember the mathematical context of previous chunks.

### 3.1 $O(1)$ In-Memory Architecture
In earlier iterations or traditional web applications, state might be delegated to an external key-value store like Redis (as seen in the project's initial experimental Docker stacks). However, given the required throughput of ~850,000 rows/second on the CINECA Galileo100 cluster, external database I/O latency would create a massive bottleneck.

To keep pace with the Rust/Polars multi-threaded engine, `DictStateMemory` utilizes native Python dictionaries. This guarantees absolute $O(1)$ algorithmic time complexity for all read and write operations, keeping memory lookups strictly within the CPU's local RAM.

### 3.2 Collision Prevention Strategy
A critical design requirement is that multiple rules might monitor the exact same sensor. For example:
* **Rule A:** Is `VOLT-MAIN` > 5V for 3 consecutive ticks?
* **Rule B:** Is `VOLT-MAIN` > 10V for 5 consecutive ticks?

To prevent these rules from overwriting each other's streaks, the class employs a composite key generation strategy via the private `_make_key` helper. The internal dictionary `_consecutive_counts` uses the string format `"{rule_id}_{sensor_id}"` (e.g., `"RULE01_VOLT-MAIN"`), ensuring strict logical isolation between overlapping rules.

### 3.3 State Tracking Pipelines
The memory module is divided into two distinct tracking pipelines to satisfy the core rules:

* **Stateful Rules (`_consecutive_counts`):**
  Stores standard integers representing the active anomaly streak. If a chunk ends with an active breach, the rules engine calls `set_consecutive_count` to stash the streak. When the next chunk begins, `get_current_count` seamlessly reinjects that integer into the Polars cumulative sum calculation.

* **Step-Difference Rules (`_last_values`):**
  To calculate $T_n - T_{n-1}$, the exact physical value of a sensor at the final timestamp of a batch must be preserved. The `_last_values` dictionary maps the raw `sensor_id` directly to a float. This provides the mathematical anchor needed by the engine to calculate the `.diff()` on the very first row of the incoming batch.

## 4. I/O Operations: Ingestion & Exportation (`reader.py` & `writer.py`)

The I/O layer handles the physical movement of data between the cluster's high-speed NVMe storage and the application's RAM. In an HPC environment processing millions of rows, I/O is typically the primary bottleneck. The `CSVTelemetryReader` and `CSVOutputWriter` modules are heavily optimized to minimize memory reallocation and bypass slow Python-level string operations.

### 4.1 Data Ingestion & Sanitization (`CSVTelemetryReader`)

The reader does more than just load CSV files; it acts as a highly optimized memory governor and strict firewall against corrupted data.

* **The Exact-Slicing Buffer Problem:**
  Polars' native `read_csv_batched` pulls data from disk in strict 50,000-row physical chunks. However, to prevent mathematical errors, the orchestrator requires *exact* batch sizes (e.g., multiples of the active sensor count) to ensure that a single timestamp is never split across two batches.
  The `extract_batch` method solves this using an internal list-buffer. Instead of iteratively concatenating small DataFrames (which causes massive $O(N^2)$ memory reallocation overhead), it appends references to a Python list, performs exactly *one* `pl.concat()`, slices the exact `batch_size` needed, and stashes the remainder in `self._buffer` for the next loop.

* **Strict Type-Checking (The Firewall):**
  Sensor data can be noisy or corrupted. The `_sanitize_batch` method guarantees that no malformed data ever reaches the Rules Engine.
  It reads all data as strings first, then attempts a strict `.cast(pl.Float64)` and a datetime parse. Any row containing non-numeric sensor values or corrupted timestamps is safely dropped (`drop_nulls`). Missing priorities are automatically patched to `LOW`. This ensures the Rust engine never panics due to unexpected `NaN` or type-mismatch errors during mathematical operations.

### 4.2 Data Exportation (`CSVOutputWriter`)

Once the Rules Engine separates the clean telemetry from the anomalies, the `CSVOutputWriter` handles formatting and saving the data to the cluster's `$WORK` directory.

* **Bypassing Python String Formatting:**
  The ESA Call for Tenders requires nominal data to be grouped by timestamp and formatted specifically (e.g., `TIMESTAMP;NOMINAL;VOLT-MAIN:5.2|TEMP:12.1`).
  Iterating through millions of rows using Python's `f-strings` or Pandas' `.apply()` would completely stall the pipeline. Instead, the writer leverages Polars' native string manipulation at the Rust level. It uses `pl.concat_str` to build the `sensor:value` pairs, groups by timestamp, and collapses the arrays using the blazing-fast `.list.join("|")` function.

* **Append-Only Disk Writes:**
  To maintain a tiny RAM footprint, the writer does not accumulate the final output in memory. Both `write_valid_batch` and `write_alarms_batch` open their respective files in append binary mode (`'ab'`). As soon as a batch is processed, it is immediately flushed to disk (`write_csv(f, ...)`), keeping the memory completely clear for the next chunk of telemetry.
