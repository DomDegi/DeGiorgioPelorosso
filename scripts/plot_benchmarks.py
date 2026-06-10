import polars as pl
import matplotlib.pyplot as plt

# 1. Read the data using Polars
df = pl.read_csv("benchmark_results_reproduced.csv")

# 2. Convert RAM from Kilobytes to Megabytes for better readability
# Polars uses .with_columns() to add new computed columns
df = df.with_columns((pl.col("Max RAM (KB)") / 1024).alias("Max RAM (MB)"))

# 3. Initialize the plot
fig, ax1 = plt.subplots(figsize=(10, 6))

# Use a logarithmic scale for the X-axis because batch sizes jump drastically
ax1.set_xscale("log")

# 4. Plot Total Execution Time (The U-Curve) on the left Y-axis
color1 = "#1f77b4"  # Blue
ax1.set_xlabel("Batch Size (Log Scale)", fontsize=12, fontweight="bold")
ax1.set_ylabel(
    "Total Execution Time (Seconds)", color=color1, fontsize=12, fontweight="bold"
)
line1 = ax1.plot(
    df["Batch Size"],
    df["Total Time (s)"],
    marker="o",
    color=color1,
    linewidth=2.5,
    label="Total Time (s)",
)
ax1.tick_params(axis="y", labelcolor=color1)
ax1.grid(True, which="both", linestyle="--", alpha=0.6)

# Highlight the sweet spot automatically
# In Polars, we find the minimum time, then filter the dataframe to get the matching batch size
min_time = df["Total Time (s)"].min()
min_batch = df.filter(pl.col("Total Time (s)") == min_time)["Batch Size"][0]

ax1.annotate(
    f"Sweet Spot\n({int(min_batch/1000)}k rows)",
    xy=(min_batch, min_time),
    xytext=(min_batch, min_time + 2),
    arrowprops=dict(facecolor="black", shrink=0.05, width=1.5, headwidth=8),
    fontsize=10,
    ha="center",
    fontweight="bold",
)

# 5. Create a second Y-axis that shares the same X-axis
ax2 = ax1.twinx()

# Plot Max RAM on the right Y-axis
color2 = "#d62728"  # Red
ax2.set_ylabel(
    "Peak Memory Required (MB)", color=color2, fontsize=12, fontweight="bold"
)
line2 = ax2.plot(
    df["Batch Size"],
    df["Max RAM (MB)"],
    marker="s",
    color=color2,
    linewidth=2.5,
    linestyle="--",
    label="Max RAM (MB)",
)
ax2.tick_params(axis="y", labelcolor=color2)

# Combine both lines into a single legend
lines = line1 + line2
labels = [line.get_label() for line in lines]
ax1.legend(lines, labels, loc="upper center", bbox_to_anchor=(0.5, 0.95))

# Title and layout cleanup
plt.title(
    "Performance vs. Batch Size\n(The U-Shaped Curve & Memory Wall)",
    fontsize=14,
    fontweight="bold",
    pad=15,
)
fig.tight_layout()

# Save the plot
plt.savefig("benchmark_plot_galileo100_32CPU_64GB.png", dpi=300)
print(
    "Plot successfully generated and saved as benchmark_plot_galileo100_32CPU_64GB.png"
)
