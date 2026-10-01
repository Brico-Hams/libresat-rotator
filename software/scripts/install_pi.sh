#!/bin/bash
# Install the LibreSat Rotator head on Raspberry Pi OS Lite (Bookworm, 32/64-bit). Run as root:
#   sudo ./install_pi.sh            (from the software/ directory of the repository)
set -euo pipefail
cd "$(dirname "$0")/.."
apt-get update
apt-get install -y python3-venv chrony openocd libhamlib-utils || apt-get install -y python3-venv chrony
id lsr >/dev/null 2>&1 || useradd -r -m -d /home/lsr -s /usr/sbin/nologin lsr
usermod -aG dialout lsr
python3 -m venv /opt/lsr/venv
/opt/lsr/venv/bin/pip install --upgrade pip
/opt/lsr/venv/bin/pip install .
mkdir -p /etc/lsr
[ -f /etc/lsr/config.yaml ] || cp scripts/config.example.yaml /etc/lsr/config.yaml
chown -R lsr:lsr /etc/lsr
# UART on the 40-pin header for the LSR-CTL board: enable it and free it from the login console
raspi-config nonint do_serial_hw 0 || true
raspi-config nonint do_serial_cons 1 || true
grep -q '^dtoverlay=disable-bt' /boot/firmware/config.txt 2>/dev/null || echo 'dtoverlay=disable-bt' >> /boot/firmware/config.txt
install -m 644 systemd/lsr.service /etc/systemd/system/lsr.service
systemctl daemon-reload
systemctl enable --now lsr
echo "Installed. Web UI: http://$(hostname).local:8080   rotctld: port 4533"
echo "Optional: sudo scripts/setup_hotspot.sh  (Wi-Fi access point for the field)"
