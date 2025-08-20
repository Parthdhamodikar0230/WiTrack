from flask import Flask, jsonify
import socket
import threading
import csv
from datetime import datetime

app = Flask(__name__)

# CSV file to store data
csv_file = 'rssi_data.csv'

# UDP settings
UDP_IP = "0.0.0.0"
UDP_PORT = 4210

# Start UDP server in a separate thread
def udp_server():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_IP, UDP_PORT))
    print(f"Listening for UDP packets on {UDP_IP}:{UDP_PORT}")

    # Open CSV and write header if file empty
    with open(csv_file, mode='a', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['timestamp_received', 'node_id', 'ssid', 'bssid', 'rssi', 'channel', 'node_timestamp'])

    while True:
        data, addr = sock.recvfrom(1024)
        message = data.decode().strip()
        print(f"Received: {message} from {addr}")

        try:
            node_id, ssid, bssid, rssi, channel, node_timestamp = message.split(',')
            timestamp_received = datetime.now().isoformat()

            with open(csv_file, mode='a', newline='') as file:
                writer = csv.writer(file)
                writer.writerow([timestamp_received, node_id, ssid, bssid, rssi, channel, node_timestamp])
        except Exception as e:
            print(f"Error processing data: {e}")

# Flask route to check server status
@app.route('/health')
def health():
    return jsonify({"status": "running"})

if __name__ == '__main__':
    threading.Thread(target=udp_server, daemon=True).start()
    app.run(host='0.0.0.0', port=5000)
