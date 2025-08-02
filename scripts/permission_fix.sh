#!/bin/bash

# Permission Fix for Turnkey Setup
echo "🔧 Fixing Permission Issues"
echo "============================"

# Make sure the updated turnkey_setup.py exists
if [ ! -f "turnkey_setup.py" ]; then
    echo "❌ Please save the updated turnkey_setup.py first!"
    echo "Copy the fixed version from Claude and save it as turnkey_setup.py"
    exit 1
fi

echo "✅ Found updated turnkey_setup.py"

# Copy the fixed setup script
echo "📄 Installing fixed setup script..."
sudo cp turnkey_setup.py /opt/powermonitor/
sudo chmod +x /opt/powermonitor/turnkey_setup.py
sudo chown pi:pi /opt/powermonitor/turnkey_setup.py

# Fix permissions on existing directories
echo "🔧 Fixing directory permissions..."
sudo mkdir -p /etc/powermonitor
sudo mkdir -p /opt/powermonitor  
sudo mkdir -p /var/log/powermonitor

sudo chown -R pi:pi /opt/powermonitor
sudo chown -R pi:pi /var/log/powermonitor

echo ""
echo "✅ Permission fixes applied!"
echo ""
echo "🚀 Now you can run the setup:"
echo "   python3 /opt/powermonitor/turnkey_setup.py"
echo ""
echo "The setup will now properly use sudo for system files."
echo ""
