import polars as pl
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

# 1. Load the data
# Assuming you downloaded 'scalability_results.csv' from the cluster to your local machine
data_file = "scalability_results.csv"
try:
    df = pl.read_csv(data_file)
except FileNotFoundError:
    print(
        f"Error: Could not find {data_file}. Please download it from the cluster first."
    )
    exit()

# 2. Setup the plot
plt.figure(figsize=(10, 6))
plt.style.use("seaborn-v0_8-whitegrid")  # Makes it look clean and professional

# 3. Plot the data
plt.plot(
    df["Rows"],
    df["Time_Seconds"],
    marker="o",
    linestyle="-",
    color="#1f77b4",
    linewidth=2,
    markersize=8,
)


# 4. Format the X-axis to show millions cleanly (e.g., 50M instead of 50000000)
def millions_formatter(x, pos):
    return f"{int(x / 1_000_000)}M"


plt.gca().xaxis.set_major_formatter(FuncFormatter(millions_formatter))

# 5. Add labels and title
plt.title("AstraLog-HPC Scalability: Execution Time vs. Data Size", fontsize=14, pad=15)
plt.xlabel("Number of Rows Processed", fontsize=12)
plt.ylabel("Execution Time (Seconds)", fontsize=12)

# Set Y-axis to start at 0 so the scale is visually honest
plt.ylim(bottom=0)

# 6. Save the plot
output_image = "scalability_plot.png"
plt.savefig(output_image, dpi=300, bbox_inches="tight")
print(f"✅ Plot successfully saved as {output_image}")

# Show the plot interactively
plt.show()
