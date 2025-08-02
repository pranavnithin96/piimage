#!/bin/bash

# Enhanced SD Card Preparation Script
echo "🔌 Preparing Enhanced SD Card for Deployment"
echo "============================================"

# Remove setup complete marker
if [ -f "/opt/powermonitor/.setup_complete" ]; then
    sudo rm /opt/powermonitor/.setup_complete
    echo "✅ Removed setup completion marker"
fi

# Remove any existing config
if [ -f "/etc/powermonitor/config.conf" ]; then
    sudo rm /etc/powermonitor/config.conf
    echo "✅ Removed existing configuration"
fi

# Stop and disable service if running
sudo systemctl stop powermonitor 2>/dev/null
sudo systemctl disable powermonitor 2>/dev/null
echo "✅ Stopped and disabled service"

# Remove any existing power monitor script
if [ -f "/opt/powermonitor/pi_monitor_script.py" ]; then
    sudo rm /opt/powermonitor/pi_monitor_script.py
    echo "✅ Removed existing monitor script"
fi

# Clean logs
sudo rm -f /var/log/powermonitor/*
sudo journalctl --rotate
sudo journalctl --vacuum-time=1s
echo "✅ Cleared log files"

# Remove SSH host keys (will be regenerated on first boot)
sudo rm -f /etc/ssh/ssh_host_*
echo "✅ Removed SSH host keys (will regenerate)"

# Clear bash history
history -c
> ~/.bash_history
echo "✅ Cleared bash history"

# Remove any temporary files
sudo rm -f /tmp/powermonitor*
echo "✅ Cleaned temporary files"

echo ""
echo "🎯 Enhanced SD Card is ready for imaging!"
echo ""
echo "Features in this image:"
echo "  ✅ Custom device naming"
echo "  ✅ Automatic timezone detection" 
echo "  ✅ 6-CT sensor monitoring"
echo "  ✅ ISO 8601 UTC timestamps"
echo "  ✅ Professional setup wizard"
echo ""
echo "Next steps:"
echo "1. Shutdown: sudo shutdown -h now"
echo "2. Create SD card image"
echo "3. Flash to new cards for deployment"
echo ""
echo "Deployment experience:"
echo "  • Flash image → Boot Pi → SSH in"
echo "  • Setup wizard runs automatically"
echo "  • User enters device name & location"
echo "  • Timezone detected automatically"
echo "  • Monitoring starts immediately"
echo ""
