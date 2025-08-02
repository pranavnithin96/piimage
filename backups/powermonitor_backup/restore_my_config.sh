#!/bin/bash

echo "🔄 Restoring Your Personal Power Monitor Configuration"
echo "=================================================="

# Stop service if running
sudo systemctl stop powermonitor 2>/dev/null

# Restore configuration
if [ -f "config.conf" ]; then
    sudo mkdir -p /etc/powermonitor
    sudo cp config.conf /etc/powermonitor/
    sudo chown pi:pi /etc/powermonitor/config.conf
    echo "✅ Configuration restored"
fi

# Restore power monitor script
if [ -f "pi_monitor_script.py" ]; then
    sudo mkdir -p /opt/powermonitor
    sudo cp pi_monitor_script.py /opt/powermonitor/
    sudo chmod +x /opt/powermonitor/pi_monitor_script.py
    sudo chown pi:pi /opt/powermonitor/pi_monitor_script.py
    echo "✅ Power monitor script restored"
fi

# Restore service
if [ -f "powermonitor.service" ]; then
    sudo cp powermonitor.service /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable powermonitor
    echo "✅ Service restored"
fi

# Mark setup as complete
sudo mkdir -p /opt/powermonitor
echo "Setup completed: $(date)" | sudo tee /opt/powermonitor/.setup_complete > /dev/null
echo "✅ Setup completion marker restored"

# Start service
sudo systemctl start powermonitor
echo "✅ Service started"

echo ""
echo "🎉 Your personal configuration has been restored!"
echo "Device should be monitoring with your original settings."
echo ""

# Show status
if systemctl is-active --quiet powermonitor; then
    echo "✅ Service is running"
    echo "📊 Monitor logs: journalctl -u powermonitor -f"
else
    echo "❌ Service failed to start"
fi
