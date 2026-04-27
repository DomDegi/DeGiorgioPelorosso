import argparse

# Import the 'orchestrator' function from the 'orchestrator.py' file
# Note: both files must be in the same folder.
from orchestrator import orchestrator 

def main():
    # Initialize the argument parser
    parser = argparse.ArgumentParser(description="Main script that calls an external orchestrator.")
    
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
    orchestrator(args.batch_size)


if __name__ == "__main__":
    main()