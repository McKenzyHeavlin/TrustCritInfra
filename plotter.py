import argparse
import matplotlib.pyplot as plt
import pandas as pd

# Parse command-line arguments
parser = argparse.ArgumentParser(description="Plot pH and Pump State from time series data.")
parser.add_argument("data_location", type=str, help="Path to the CSV data file")
args = parser.parse_args()

# Load data from the CSV file
data = pd.read_csv(args.data_location)

# Dynamically set headers based on the number of columns
if data.shape[1] == 3:
    data.columns = ["Time", "pH", "Pump State"]
elif data.shape[1] == 2:
    data.columns = ["Time", "pH"]
else:
    raise ValueError("Unsupported number of columns in the data file. Expected 2 or 3 columns.")

# Convert time to relative time (starting from 0)
data["Time"] -= data["Time"].min()

# Convert pump state to numeric for plotting if the column exists
if "Pump State" in data.columns:
    data["Pump State"] = data["Pump State"].map(lambda x: 1 if x == True else 0)

# Create the figure and primary y-axis
fig, ax1 = plt.subplots(figsize=(10, 6))

# Plot pH vs. Time
ax1.plot(data["Time"], data["pH"], label="pH", color="blue", marker="o")
ax1.set_xlabel("Time (s)")
ax1.set_ylabel("pH", color="blue")
ax1.tick_params(axis="y", labelcolor="blue")

# Create the secondary y-axis if Pump State exists
if "Pump State" in data.columns:
    ax2 = ax1.twinx()
    ax2.step(data["Time"], data["Pump State"], label="Pump State", color="red", where="post")
    ax2.set_ylabel("Pump State (ON/OFF)", color="red")
    ax2.tick_params(axis="y", labelcolor="red")
    ax2.set_yticks([0, 1])
    ax2.set_yticklabels(["OFF", "ON"])

# Add grid and title
plt.title("pH vs. Time with Pump State Overlay")
fig.tight_layout()

# Add legends
ax1.legend(loc="upper left")
if "Pump State" in data.columns:
    ax2.legend(loc="upper right")

# Show plot
plt.show()
