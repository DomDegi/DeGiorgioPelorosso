import argparse

# Import the 'orchestrator' function from the 'orchestrator.py' file
# Note: both files must be in the same folder.
from orchestrator import orchestrator 

def main():
    # Define the input and output paths
    input_path = "csv_input/export_sat_alpha_small.csv"
    output_path = "csv_output/"

    # Initialize the argument parser
    parser = argparse.ArgumentParser(description="Main script with hardcoded paths and command-line argument for batch size.")
    
    # Define the expected argument
    parser.add_argument(
        '--batch_size', 
        type=int, 
        required=True, 
        help="Specifies the batch size (integer)."
    )
    
    # Parse the arguments passed from the terminal
    args = parser.parse_args()
    
    # Call the imported function passing the argument
    orchestrator(
        batch_size=args.batch_size, 
        input_path=input_path, 
        output_path=output_path
    )


if __name__ == "__main__":
    main()