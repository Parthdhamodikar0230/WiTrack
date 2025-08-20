# analysis_single_node.py
# RSSI distance analysis for a single node setup.
# Inputs:
#   - rssi_data.csv with header:
#       timestamp_received,node_id,ssid,bssid,rssi,channel,node_timestamp
#   - nodes.json (optional) with one entry:
#       {"id":"node1","P0":-55.0,"n":3.0}
# Outputs:
#   - distances.csv       (per-device, per-time-bin distances in meters)
#   - distance_plot.png   (distance over time for top devices)

import os
import sys
import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# Config
CSV_IN = "rssi_data.csv"
NODES_JSON = "nodes.json"
DISTANCES_OUT = "distances.csv"
PLOT_OUT = "distance_plot.png"

TIME_BIN = "2S"      # time bin for aggregating RSSI
ROLL_WINDOW = "10S"  # smoothing window
RSSI_MIN = -95
RSSI_MAX = -20

# Load calibration (optional)
P0 = -55.0
n = 3.0
if os.path.exists(NODES_JSON):
    try:
        cfg = json.load(open(NODES_JSON))
        # If array, take first entry
        entry = cfg[0] if isinstance(cfg, list) else cfg
        if entry.get("id") and ("P0" in entry) and ("n" in entry):
            P0 = float(entry["P0"])
            n  = float(entry["n"])
            print(f"Using calibration P0={P0}, n={n}")
    except Exception:
        print("Warning: failed to parse nodes.json; using defaults")

# Load and clean
df = pd.read_csv(CSV_IN)
required = {"timestamp_received","bssid","rssi"}
if not required.issubset(df.columns):
    print(f"Error: CSV must have columns {required}")
    sys.exit(1)

df = df.dropna(subset=["timestamp_received","bssid","rssi"])
df["t"] = pd.to_datetime(df["timestamp_received"], errors="coerce")
df = df.dropna(subset=["t"])
df["rssi"] = pd.to_numeric(df["rssi"], errors="coerce")
df = df.dropna(subset=["rssi"])
df = df[(df["rssi"] >= RSSI_MIN) & (df["rssi"] <= RSSI_MAX)]
df = df.sort_values("t")

# Smooth RSSI per device
df["t_bin"] = df["t"].dt.floor(TIME_BIN)
def smooth_group(g):
    g = g.sort_values("t").set_index("t")
    g["rssi_smooth"] = g["rssi"].rolling(ROLL_WINDOW, min_periods=1).median()
    return g.reset_index()
df = df.groupby("bssid", group_keys=False).apply(smooth_group)

# Estimate distance per record: d=10^((P0-RSSI)/(10*n))
df["distance_m"] = np.power(10.0, (P0 - df["rssi_smooth"]) / (10.0 * n))
df["distance_m"] = df["distance_m"].round(2)

# Aggregate per device/time bin: mean distance
out = (
    df.groupby(["bssid","t_bin"], as_index=False)
      .distance_m.mean()
      .rename(columns={"distance_m":"avg_distance_m"})
)
out.to_csv(DISTANCES_OUT, index=False)
print(f"Wrote distances to {DISTANCES_OUT}")

# Plot top 3 devices
top_devices = out["bssid"].value_counts().nlargest(3).index
plt.figure(figsize=(10,5))
for dev in top_devices:
    sub = out[out["bssid"] == dev]
    plt.plot(sub["t_bin"], sub["avg_distance_m"], marker="o", label=dev)
plt.xlabel("Time")
plt.ylabel("Distance (m)")
plt.title("Distance over Time (top 3 devices)")
plt.legend()
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig(PLOT_OUT, dpi=150)
plt.close()
print(f"Wrote plot to {PLOT_OUT}")
