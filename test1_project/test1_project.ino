#include <ESP8266WiFi.h>
#include <WiFiUdp.h>

const char* ssid = "vivo Y72 5G";        // Replace with your WiFi SSID
const char* password = "griffinmoss+6972"; // Replace with your WiFi Password

const char* udpAddress = "172.17.168.60";   // Replace with your laptop IP
const int udpPort = 4210;                  // UDP port your server will listen on

WiFiUDP udp;

void setup() {
  Serial.begin(115200);
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);
  Serial.println("Connecting to WiFi...");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nConnected to WiFi");
}

void loop() {
  int n = WiFi.scanNetworks();
  Serial.printf("Scan done, %d networks found\n", n);
  for (int i = 0; i < n; ++i) {
    String ssid = WiFi.SSID(i);
    String bssid = WiFi.BSSIDstr(i);
    int32_t rssi = WiFi.RSSI(i);
    int32_t channel = WiFi.channel(i);

    // Format data as CSV: node_id, ssid, bssid, rssi, channel, timestamp
    String data = String("node1,") + ssid + "," + bssid + "," + rssi + "," + channel + "," + String(millis()) + "\n";

    // Send via UDP
    udp.beginPacket(udpAddress, udpPort);
    udp.write((const uint8_t*)data.c_str(), data.length());
    udp.endPacket();

    Serial.print("Sent: ");
    Serial.print(data);
  }
  delay(5000); // Scan every 5 seconds
}
