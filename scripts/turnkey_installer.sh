#!/bin/bash

# Turnkey Power Monitor SD Card Setup
echo "🔌 Turnkey Power Monitor SD Card Setup"
echo "======================================"
echo "Creating reusable SD card image for multiple deployments"

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   echo "Please run this script as regular user (pi), not root"
   exit 1
fi

# Install required packages
echo "📦 Installing required packages..."
sudo apt update
sudo apt install -y python3-pip python3-spidev python3-requests python3-curses python3-uuid

# Install Python packages
pip3 install requests spidev

# Create directories
echo "📁 Creating directories..."
sudo mkdir -p /opt/powermonitor
sudo mkdir -p /etc/powermonitor
sudo mkdir -p /var/log/powermonitor

# Copy the turnkey setup script
echo "📄 Installing turnkey setup script..."
if [ ! -f "turnkey_setup.py" ]; then
    echo "❌ turnkey_setup.py not found!"
    echo "Please save the turnkey setup script as 'turnkey_setup.py' first"
    exit 1
fi

sudo cp turnkey_setup.py /opt/powermonitor/
sudo chmod +x /opt/powermonitor/turnkey_setup.py

# Create the auto-run script for SSH login
echo "🔑 Setting up automatic setup on SSH login..."
sudo tee /opt/powermonitor/auto_setup.sh > /dev/null << 'EOF'
#!/bin/bash

# Auto-run setup script on SSH login
# Only runs for interactive SSH sessions and if setup is not complete

if [[ -n "$SSH_CONNECTION" ]] && [[ $- == *i* ]]; then
    # Check if setup is complete
    if [ ! -f "/opt/powermonitor/.setup_complete" ]; then
        echo ""
        echo "🔌 Welcome to Power Monitor!"
        echo "Starting automatic configuration..."
        echo ""
        python3 /opt/powermonitor/turnkey_setup.py
        
        # If setup completed successfully, show success message
        if [ -f "/opt/powermonitor/.setup_complete" ]; then
            echo ""
            echo "🎉 Power Monitor is now configured and running!"
            echo "You can monitor it with: journalctl -u powermonitor -f"
            echo ""
        fi
    else
        # Setup already complete, show status
        echo ""
        echo "🔌 Power Monitor Status:"
        
        # Check service status
        if systemctl is-active --quiet powermonitor; then
            echo "✅ Service is running"
            echo "📊 Monitor logs: journalctl -u powermonitor -f"
        else
            echo "❌ Service is not running"
            echo "🔧 Start with: sudo systemctl start powermonitor"
        fi
        echo ""
    fi
fi
EOF

sudo chmod +x /opt/powermonitor/auto_setup.sh

# Add to bashrc for pi user (only if not already present)
if ! grep -q "auto_setup.sh" ~/.bashrc; then
    echo "" >> ~/.bashrc
    echo "# Power Monitor Auto-Setup" >> ~/.bashrc
    echo "/opt/powermonitor/auto_setup.sh" >> ~/.bashrc
    echo "✅ Added auto-setup to SSH login"
else
    echo "ℹ️  Auto-setup already configured in bashrc"
fi

# Set permissions
sudo chown -R pi:pi /opt/powermonitor
sudo chown -R pi:pi /var/log/powermonitor

# Enable SPI interface
echo "🔌 Enabling SPI interface..."
sudo raspi-config nonint do_spi 0

# Create a status check script
echo "🔧 Creating status check script..."
sudo tee /opt/powermonitor/check_status.py > /dev/null << 'EOF'
#!/usr/bin/env python3

import subprocess
import os
from datetime import datetime

def check_setup_status():
    print("🔌 Power Monitor Status Check")
    print("=" * 40)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Check if setup is complete
    setup_complete = os.path.exists("/opt/powermonitor/.setup_complete")
    print(f"Setup Complete: {'✅ Yes' if setup_complete else '❌ No'}")
    
    if not setup_complete:
        print("Run setup with: python3 /opt/powermonitor/turnkey_setup.py")
        return
    
    # Check service status
    try:
        result = subprocess.run(['systemctl', 'is-active', 'powermonitor'], 
                              capture_output=True, text=True)
        status = result.stdout.strip()
        
        if status == 'active':
            print("Service Status: ✅ Running")
        elif status == 'inactive':
            print("Service Status: 🔴 Stopped")
        else:
            print(f"Service Status: 🟡 {status}")
    except:
        print("Service Status: ❓ Unknown")
    
    # Check config
    try:
        with open('/etc/powermonitor/config.conf', 'r') as f:
            config_lines = f.readlines()
        
        print("\nConfiguration:")
        for line in config_lines:
            if '=' in line and not line.strip().startswith('#'):
                key, value = line.strip().split('=', 1)
                if key in ['DEVICE_ID', 'LOCATION_NAME', 'VOLTAGE', 'CT_RATING']:
                    print(f"  {key}: {value}")
    except:
        print("Configuration: ❌ Not found")
    
    print("\nCommands:")
    print("  sudo systemctl start powermonitor    # Start service")
    print("  sudo systemctl stop powermonitor     # Stop service")
    print("  journalctl -u powermonitor -f        # View live logs")
    print("  python3 /opt/powermonitor/check_status.py  # This status check")

if __name__ == "__main__":
    check_setup_status()
EOF

sudo chmod +x /opt/powermonitor/check_status.py

# Create SD card preparation script
echo "💾 Creating SD card preparation script..."
sudo tee /opt/powermonitor/prepare_sd_card.sh > /dev/null << 'EOF'
#!/bin/bash

# SD Card Preparation Script
# Run this before creating SD card image

echo "🔌 Preparing SD Card for Deployment"
echo "==================================="

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
echo "✅ Cleared log files"

# Remove SSH host keys (will be regenerated on first boot)
sudo rm -f /etc/ssh/ssh_host_*
echo "✅ Removed SSH host keys (will regenerate)"

# Clear bash history
history -c
> ~/.bash_history
echo "✅ Cleared bash history"

echo ""
echo "🎯 SD Card is now ready for imaging!"
echo ""
echo "Next steps:"
echo "1. Shutdown the Pi: sudo shutdown -h now"
echo "2. Remove SD card and create image"
echo "3. Flash image to new SD cards for deployment"
echo ""
echo "When new Pi boots up:"
echo "- SSH into the Pi"
echo "- Setup wizard will run automatically"
echo "- Configure WiFi, CT rating, voltage"
echo "- Service starts automatically"
echo ""
EOF

sudo chmod +x /opt/powermonitor/prepare_sd_card.sh

echo ""
echo "✅ Turnkey SD Card Setup Complete!"
echo ""
echo "🎯 What's installed:"
echo "   • Automatic setup wizard on SSH login"
echo "   • WiFi configuration interface" 
echo "   • CT rating and voltage selection"
echo "   • Automatic service installation"
echo "   • Status monitoring tools"
echo ""
echo "🚀 Testing the setup:"
echo "   python3 /opt/powermonitor/turnkey_setup.py"
echo ""
echo "🔧 Utility scripts:"
echo "   /opt/powermonitor/check_status.py     # Check current status"
echo "   /opt/powermonitor/prepare_sd_card.sh  # Prepare for imaging"
echo ""
echo "💾 To create deployable SD card image:"
echo "   1. Test the setup works"
echo "   2. Run: /opt/powermonitor/prepare_sd_card.sh"
echo "   3. Shutdown and create SD card image"
echo "   4. Flash to new cards for deployment"
echo ""
echo "📋 Deployment process:"
echo "   1. Flash SD card with your image"
echo "   2. Boot Pi and SSH into it"
echo "   3. Setup wizard runs automatically"
echo "   4. Configure and start monitoring"
echo ""
