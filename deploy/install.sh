#!/usr/bin/env bash
# Installs the assistant as a systemd service on a Raspberry Pi.
# Run from the project folder: sudo bash deploy/install.sh
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
    echo "Run with sudo." >&2
    exit 1
fi

APP_DIR=/opt/drowsiness-assistant
SERVICE_USER=${SUDO_USER:-pi}
SRC_DIR=$(cd "$(dirname "$0")/.." && pwd)

mkdir -p "$APP_DIR"
cp -r "$SRC_DIR"/. "$APP_DIR"/
chown -R "$SERVICE_USER":"$SERVICE_USER" "$APP_DIR"

sudo -u "$SERVICE_USER" python3 -m venv "$APP_DIR/.venv"
sudo -u "$SERVICE_USER" "$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements-device.txt" -r "$APP_DIR/requirements-pi.txt"

usermod -aG video,gpio "$SERVICE_USER"

sed "s/^User=.*/User=$SERVICE_USER/" "$APP_DIR/deploy/drowsiness-assistant.service" \
    > /etc/systemd/system/drowsiness-assistant.service
cp "$APP_DIR/deploy/drowsiness.logrotate" /etc/logrotate.d/drowsiness

systemctl daemon-reload
systemctl enable --now drowsiness-assistant.service

echo "Installed. Status: systemctl status drowsiness-assistant"
echo "Logs: journalctl -u drowsiness-assistant -f   and   /var/log/drowsiness/drive.csv"
