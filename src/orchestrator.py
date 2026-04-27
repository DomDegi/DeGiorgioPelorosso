import pandas as pd

# 1. Import the Interfaces (Abstract Base Classes)
# Assuming the provided abstract classes are saved in 'interfaces.py'
from interfaces import ITelemetryReader, IRulesEngine, IOutputWriter

# 2. Import the Concrete Implementations from your existing files
from reader import CSVTelemetryReader
from rules_engine import PandasRulesEngine
from writer import CSVOutputWriter


def orchestrator(batch_size: int, input_path: str, output_path: str) -> None:
    """
    Main orchestration loop that ties the system components together.
    It relies entirely on interfaces to interact with the underlying components.
    """
    print("--- AstraLog-HPC Orchestrator Started ---")
    print(f"Batch Size : {batch_size}")
    print(f"Input Path : {input_path}")
    print(f"Output Path: {output_path}")
    print("-----------------------------------------\n")

    # --- COMPONENT INSTANTIATION ---
    # Here we instantiate the concrete classes, but we type-hint them 
    # strictly as their Interfaces. This is the Python equivalent of Java's:
    # ITelemetryReader reader = new CSVTelemetryReader(input_path);
    
    reader: ITelemetryReader = CSVTelemetryReader(input_path)
    rules_engine: IRulesEngine = PandasRulesEngine()
    writer: IOutputWriter = CSVOutputWriter(output_path)

    batch_counter = 0

    # --- MAIN ORCHESTRATION LOOP ---
    while True:
        # 1. Extract the next batch of telemetry
        # The reader converts a physical chunk into a logical DataFrame batch
        telemetry_batch: pd.DataFrame = reader.extract_batch(batch_size)

        # Check for End of File (EOF)
        if telemetry_batch.empty:
            print("\n[INFO] EOF reached. No more telemetry to process.")
            break

        batch_counter += 1
        print(f"Processing Batch #{batch_counter} (Rows: {len(telemetry_batch)})...")

        # 2. Evaluate business logic
        # The Rules Engine separates nominal data from anomalies
        valid_telemetry, alarm_telemetry = rules_engine.evaluate_rules(telemetry_batch)

        # 3. Write outputs
        # The Writer handles the physical I/O chunking to the disk
        if not valid_telemetry.empty:
            writer.write_valid_batch(valid_telemetry)

        if not alarm_telemetry.empty:
            writer.write_alarms_batch(alarm_telemetry)

    print("\n--- AstraLog-HPC Orchestrator Finished ---")
    print(f"Total batches processed: {batch_counter}")