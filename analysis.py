# analysis_enhanced.py
# Enhanced RSSI analysis with detailed WiFi information in table format
# Inputs:
#   - rssi_data.csv with header:
#       timestamp_received,node_id,ssid,bssid,rssi,channel,node_timestamp
#   - nodes.json (optional) with calibration data
# Outputs:
#   - wifi_devices_table.csv    (detailed device information table)
#   - distance_summary.csv      (distance statistics per device)
#   - distance_plot.png         (distance over time visualization)
#   - wifi_summary_report.txt   (human-readable summary)

import os
import sys
import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime

# Config
CSV_IN = "rssi_data.csv"
NODES_JSON = "nodes.json"
WIFI_TABLE_OUT = "wifi_devices_table.csv"
DISTANCE_SUMMARY_OUT = "distance_summary.csv" 
PLOT_OUT = "distance_plot.png"
REPORT_OUT = "wifi_summary_report.txt"

TIME_BIN = "2S"
ROLL_WINDOW = "10S"
RSSI_MIN = -95
RSSI_MAX = -20

# Load calibration
P0 = -55.0
n = 3.0
if os.path.exists(NODES_JSON):
    try:
        cfg = json.load(open(NODES_JSON))
        entry = cfg[0] if isinstance(cfg, list) else cfg
        if entry.get("P0") and entry.get("n"):
            P0 = float(entry["P0"])
            n = float(entry["n"])
            print(f"Using calibration: P0={P0} dBm, n={n}")
    except Exception as e:
        print(f"Warning: Could not parse nodes.json: {e}")

def load_and_clean_data():
    """Load and clean the RSSI data"""
    if not os.path.exists(CSV_IN):
        print(f"Error: {CSV_IN} not found")
        sys.exit(1)
    
    df = pd.read_csv(CSV_IN)
    required = {"timestamp_received", "bssid", "rssi"}
    if "ssid" in df.columns:
        required.add("ssid")
    
    if not required.issubset(df.columns):
        print(f"Error: CSV must have columns {required}")
        sys.exit(1)
    
    # Clean data
    df = df.dropna(subset=["timestamp_received", "bssid", "rssi"])
    df["t"] = pd.to_datetime(df["timestamp_received"], errors="coerce")
    df = df.dropna(subset=["t"])
    df["rssi"] = pd.to_numeric(df["rssi"], errors="coerce")
    df = df.dropna(subset=["rssi"])
    df = df[(df["rssi"] >= RSSI_MIN) & (df["rssi"] <= RSSI_MAX)]
    
    # Handle missing SSID
    if "ssid" not in df.columns:
        df["ssid"] = "Unknown"
    df["ssid"] = df["ssid"].fillna("Hidden/Unknown")
    
    # Handle channel
    if "channel" in df.columns:
        df["channel"] = pd.to_numeric(df["channel"], errors="coerce")
    else:
        df["channel"] = np.nan
    
    df = df.sort_values("t")
    print(f"Loaded {len(df)} records after cleaning")
    return df

def smooth_rssi_data(df):
    """Apply smoothing to RSSI values"""
    df["t_bin"] = df["t"].dt.floor(TIME_BIN)
    
    def smooth_group(g):
        g = g.sort_values("t").set_index("t")
        g["rssi_smooth"] = g["rssi"].rolling(ROLL_WINDOW, min_periods=1).median()
        return g.reset_index()
    
    df = df.groupby("bssid", group_keys=False).apply(smooth_group)
    return df

def calculate_distances(df):
    """Calculate distances using path-loss model"""
    df["distance_m"] = np.power(10.0, (P0 - df["rssi_smooth"]) / (10.0 * n))
    df["distance_m"] = df["distance_m"].round(2)
    return df

def create_wifi_devices_table(df):
    """Create comprehensive WiFi devices table"""
    # Aggregate per device
    device_stats = []
    
    for bssid, group in df.groupby("bssid"):
        ssid = group["ssid"].mode().iloc[0] if not group["ssid"].mode().empty else "Unknown"
        
        # Basic stats
        first_seen = group["t"].min()
        last_seen = group["t"].max()
        duration = (last_seen - first_seen).total_seconds() / 60  # minutes
        
        # RSSI stats
        rssi_min = group["rssi_smooth"].min()
        rssi_max = group["rssi_smooth"].max()
        rssi_avg = group["rssi_smooth"].mean()
        
        # Distance stats
        dist_min = group["distance_m"].min()
        dist_max = group["distance_m"].max()
        dist_avg = group["distance_m"].mean()
        
        # Channel info
        channels = group["channel"].dropna().unique()
        channel_list = ", ".join(map(str, sorted(channels))) if len(channels) > 0 else "Unknown"
        
        # Activity stats
        total_packets = len(group)
        avg_packets_per_min = total_packets / max(duration, 1)
        
        # Classification
        if dist_avg < 2:
            proximity = "Very Close"
        elif dist_avg < 5:
            proximity = "Close"
        elif dist_avg < 10:
            proximity = "Medium"
        else:
            proximity = "Far"
        
        device_stats.append({
            "BSSID": bssid,
            "SSID/Device_Name": ssid,
            "First_Seen": first_seen.strftime("%Y-%m-%d %H:%M:%S"),
            "Last_Seen": last_seen.strftime("%Y-%m-%d %H:%M:%S"),
            "Duration_Minutes": f"{duration:.1f}",
            "Total_Packets": total_packets,
            "Packets_Per_Minute": f"{avg_packets_per_min:.1f}",
            "Channel(s)": channel_list,
            "RSSI_Min_dBm": f"{rssi_min:.1f}",
            "RSSI_Max_dBm": f"{rssi_max:.1f}",
            "RSSI_Avg_dBm": f"{rssi_avg:.1f}",
            "Distance_Min_m": f"{dist_min:.2f}",
            "Distance_Max_m": f"{dist_max:.2f}",
            "Distance_Avg_m": f"{dist_avg:.2f}",
            "Proximity_Zone": proximity,
            "Signal_Strength": "Strong" if rssi_avg > -50 else "Medium" if rssi_avg > -70 else "Weak"
        })
    
    devices_df = pd.DataFrame(device_stats)
    devices_df = devices_df.sort_values("Distance_Avg_m")
    devices_df.to_csv(WIFI_TABLE_OUT, index=False)
    print(f"Created WiFi devices table: {WIFI_TABLE_OUT}")
    return devices_df

def create_distance_summary(df):
    """Create distance summary statistics"""
    summary_data = []
    
    for bssid, group in df.groupby("bssid"):
        ssid = group["ssid"].mode().iloc[0] if not group["ssid"].mode().empty else "Unknown"
        
        # Time-binned distances
        binned = group.groupby("t_bin")["distance_m"].mean().reset_index()
        
        summary_data.append({
            "BSSID": bssid,
            "SSID": ssid,
            "Time_Points": len(binned),
            "Min_Distance_m": binned["distance_m"].min(),
            "Max_Distance_m": binned["distance_m"].max(),
            "Avg_Distance_m": binned["distance_m"].mean(),
            "Std_Distance_m": binned["distance_m"].std(),
            "Distance_Range_m": binned["distance_m"].max() - binned["distance_m"].min()
        })
    
    summary_df = pd.DataFrame(summary_data)
    summary_df = summary_df.round(2)
    summary_df.to_csv(DISTANCE_SUMMARY_OUT, index=False)
    print(f"Created distance summary: {DISTANCE_SUMMARY_OUT}")
    return summary_df

def create_visualization(df):
    """Create enhanced distance visualization"""
    # Get top 5 devices by packet count
    top_devices = df["bssid"].value_counts().nlargest(5).index
    
    plt.figure(figsize=(14, 8))
    
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']
    
    for i, bssid in enumerate(top_devices):
        device_data = df[df["bssid"] == bssid]
        ssid = device_data["ssid"].mode().iloc[0] if not device_data["ssid"].mode().empty else "Unknown"
        
        # Group by time bin and average
        binned = device_data.groupby("t_bin")["distance_m"].mean().reset_index()
        
        label = f"{ssid[:15]}{'...' if len(ssid) > 15 else ''} ({bssid[-8:]})"
        plt.plot(binned["t_bin"], binned["distance_m"], 
                marker="o", linewidth=2, color=colors[i % len(colors)], label=label)
    
    plt.xlabel("Time", fontsize=12)
    plt.ylabel("Distance (meters)", fontsize=12)
    plt.title("WiFi Device Distance Tracking Over Time", fontsize=14, fontweight='bold')
    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(PLOT_OUT, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"Created visualization: {PLOT_OUT}")

def generate_report(devices_df, summary_df, df):
    """Generate human-readable summary report"""
    with open(REPORT_OUT, 'w') as f:
        f.write("=" * 60 + "\n")
        f.write("WIFI DEVICE TRACKING ANALYSIS REPORT\n")
        f.write("=" * 60 + "\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Analysis Period: {df['t'].min()} to {df['t'].max()}\n")
        f.write(f"Total Duration: {(df['t'].max() - df['t'].min()).total_seconds()/3600:.1f} hours\n\n")
        
        f.write("SUMMARY STATISTICS:\n")
        f.write("-" * 20 + "\n")
        f.write(f"Total Devices Detected: {len(devices_df)}\n")
        f.write(f"Total Packets Captured: {len(df)}\n")
        f.write(f"Calibration Used: P0={P0} dBm, n={n}\n\n")
        
        f.write("PROXIMITY ZONES:\n")
        f.write("-" * 15 + "\n")
        proximity_counts = devices_df["Proximity_Zone"].value_counts()
        for zone, count in proximity_counts.items():
            f.write(f"{zone}: {count} devices\n")
        f.write("\n")
        
        f.write("TOP 5 CLOSEST DEVICES:\n")
        f.write("-" * 25 + "\n")
        top_5 = devices_df.nsmallest(5, "Distance_Avg_m")
        for _, row in top_5.iterrows():
            f.write(f"{row['SSID/Device_Name'][:20]:20} | {row['BSSID']} | {row['Distance_Avg_m']}m avg\n")
        f.write("\n")
        
        f.write("CHANNEL DISTRIBUTION:\n")
        f.write("-" * 20 + "\n")
        if "channel" in df.columns:
            channel_counts = df["channel"].value_counts().head(10)
            for channel, count in channel_counts.items():
                if not pd.isna(channel):
                    f.write(f"Channel {int(channel)}: {count} packets\n")
        f.write("\n")
        
        f.write("DISTANCE RANGES:\n")
        f.write("-" * 15 + "\n")
        f.write(f"Closest device: {summary_df['Min_Distance_m'].min():.2f}m\n")
        f.write(f"Farthest device: {summary_df['Max_Distance_m'].max():.2f}m\n")
        f.write(f"Average distance: {summary_df['Avg_Distance_m'].mean():.2f}m\n")
    
    print(f"Generated report: {REPORT_OUT}")

def main():
    print("Enhanced WiFi Device Analysis Starting...")
    print("=" * 50)
    
    # Load and process data
    df = load_and_clean_data()
    df = smooth_rssi_data(df)
    df = calculate_distances(df)
    
    # Generate outputs
    devices_df = create_wifi_devices_table(df)
    summary_df = create_distance_summary(df)
    create_visualization(df)
    generate_report(devices_df, summary_df, df)
    
    print("\n" + "=" * 50)
    print("Analysis Complete! Generated files:")
    print(f"📊 {WIFI_TABLE_OUT} - Detailed device table")
    print(f"📈 {DISTANCE_SUMMARY_OUT} - Distance statistics")
    print(f"📉 {PLOT_OUT} - Distance visualization")
    print(f"📄 {REPORT_OUT} - Summary report")
    
    # Quick preview
    print(f"\nQuick Preview - Found {len(devices_df)} devices:")
    print(devices_df[["SSID/Device_Name", "BSSID", "Distance_Avg_m", "Proximity_Zone"]].head(10).to_string(index=False))

if __name__ == "__main__":
    main()

