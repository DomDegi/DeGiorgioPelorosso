import argparse
import time
from src.orchestrator import orchestrator 

def main():
    input_path = "csv_input/export_sat_alpha_custom.csv"
    output_path = "output/"
    rules_path = "config/Current_rules_sat_alpha.json"
    sensors_path = "config/Current_sensors_sat_alpha.yaml"

    parser = argparse.ArgumentParser(description="AstraLog-HPC Main Execution Script")
    
    # In HPC environments, batch_size is critical to tune RAM consumption.
    parser.add_argument(
        '--batch_size', 
        type=int, 
        required=True, 
        help="Specifies the batch size (integer) for RAM-safe processing."
    )
    
    args = parser.parse_args()
    
    # Start the timer for performance benchmarking
    start_time = time.perf_counter()
    
    # Call the orchestrator passing ALL required arguments
    orchestrator(
        batch_size=args.batch_size, 
        input_path=input_path, 
        output_path=output_path,
        rules_path=rules_path,
        sensors_path=sensors_path
    )
    
    end_time = time.perf_counter()
    print(f"⏱️ Total Execution Time: {end_time - start_time:.4f} seconds")

if __name__ == "__main__":
    main()
