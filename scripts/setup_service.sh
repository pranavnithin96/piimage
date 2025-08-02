#!/bin/bash

# Simple Power Monitor Service Setup
echo "Setting up Power Monitor as a Service"
echo "====================================="

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   echo "Please run this script as regular user (pi), not root"
   exit 1
fi

# Check if power monitor script exists
if [ ! -f "pi_monitor_script.py" ]; then
    echo "ERROR: pi_monitor_script.py not found in current directory"
    echo "Please make sure your script is in the current directory"
    exit 1
fi

echo "Found pi_monitor_script.py"

# Create directories
echo "Creating service directories..."
sudo mkdir -p /opt/powermonitor
sudo mkdir -p /var/log/powermonitor

# Copy the power monitor script
echo "Installing power monitor script..."
sudo cp pi_monitor_script.py /opt/powermonitor/
sudo chmod +x /opt/powermonitor/pi_monitor_script.py

# Create systemd service file
echo "Creating systemd service..."
sudo tee /etc/systemd/system/powermonitor.service > /dev/null << 'EOF'
[Unit]
Description=Power Monitor Service
After=network.target
Wants=network.target

[Service]
Type=simple
User=pi
Group=pi
WorkingDirectory=/opt/powermonitor
ExecStart=/usr/bin/python3 /opt/powermonitor/pi_monitor_script.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Set permissions
sudo chown -R pi:pi /opt/powermonitor
sudo chown -R pi:pi /var/log/powermonitor

# Reload systemd daemon
echo "Reloading systemd..."
sudo systemctl daemon-reload

echo ""
echo "Service installation complete!"
echo ""
echo "Next steps:"
echo "  sudo systemctl enable powermonitor    # Enable auto-start"
echo "  sudo systemctl start powermonitor     # Start now"
echo "  sudo systemctl status powermonitor    # Check status"
echo "  journalctl -u powermonitor -f         # View live logs"
echo ""
