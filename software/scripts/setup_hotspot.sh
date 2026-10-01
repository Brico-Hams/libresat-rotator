#!/bin/bash
# Field Wi-Fi access point with NetworkManager (Raspberry Pi OS Bookworm).
#   sudo ./setup_hotspot.sh [SSID] [PASSWORD]
# The phone joins the SSID and opens http://10.42.0.1:8080 . Gpredict / Look4Sat: rotctld at 10.42.0.1:4533.
# The AP comes up automatically when no known Wi-Fi network is in range.
set -euo pipefail
SSID=${1:-LibreSat-Rotator}
PASS=${2:-satellite73}
nmcli con delete lsr-hotspot >/dev/null 2>&1 || true
nmcli con add type wifi ifname wlan0 con-name lsr-hotspot autoconnect yes ssid "$SSID" \
  802-11-wireless.mode ap 802-11-wireless.band bg ipv4.method shared ipv6.method disabled \
  wifi-sec.key-mgmt wpa-psk wifi-sec.psk "$PASS" connection.autoconnect-priority -10
echo "Hotspot '$SSID' configured (password: $PASS). Home Wi-Fi networks keep priority when in range."
