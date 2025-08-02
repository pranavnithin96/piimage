#!/bin/bash
set -e # Exit immediately if a command exits with a non-zero status.

echo ">>> Starting Raspberry Pi setup for Power Monitor (Global Pip Install) <<<"

# 1. Update and Upgrade System Packages
echo
echo ">>> Updating package lists..."
sudo apt-get update
echo
echo ">>> Upgrading installed packages (this may take a while)..."
sudo apt-get upgrade -y

# 2. Install Essential Dependencies
echo
echo ">>> Installing Python3, pip, git, and SPI development files..."
# python3-venv is removed as it's not needed for global install
sudo apt-get install -y python3 python3-pip python3-dev git build-essential

# 3. Enable SPI Interface
echo
echo ">>> Enabling SPI interface via raspi-config..."
if sudo raspi-config nonint get_spi | grep -q "0"; then # 0 means enabled
    echo "SPI interface is already enabled."
else
    sudo raspi-config nonint do_spi 0 # 0 means enable SPI
    echo "SPI interface enabled. A reboot will be required for hardware changes to take full effect."
fi

# Add current user to the spi and gpio groups
# This might require a logout/login or reboot to take effect.
echo
echo ">>> Adding current user ($USER) to spi and gpio groups..."
sudo usermod -a -G spi,gpio $USER || echo "Warning: Could not add user $USER to spi/gpio groups. This might require manual setup or a reboot first."

# 4. Application Setup Directory
APP_DIR="/home/$USER/powermonitor_client"
echo
echo ">>> Creating application directory: $APP_DIR..."
mkdir -p "$APP_DIR"
# User will be instructed to cd into it later.

# 5. Install Python Dependencies Globally
echo
echo ">>> Installing Python dependencies (requests, spidev) globally..."
sudo pip3 install requests spidev

echo
echo "--------------------------------------------------------------------"
echo ">>> System Setup and Global Python Packages Installation Complete! <<<"
echo "--------------------------------------------------------------------"
echo "NEXT STEPS (IMPORTANT):"
echo "1. COPY YOUR FILES:"
echo "   Manually copy your 'power_monitor_script.py' and 'config.ini' files"
echo "   into the '$APP_DIR' directory on your Raspberry Pi."
echo "   You can use 'scp' from another computer, or 'git clone' if they are in a repository."
echo
echo "2. REBOOT RECOMMENDED:"
echo "   A reboot is highly recommended for SPI and group changes to take full effect:"
echo "   sudo reboot"
echo
echo "3. AFTER REBOOT, TO RUN YOUR SCRIPT:"
echo "   Navigate to your application directory:"
echo "   cd $APP_DIR"
echo "   Make your script executable (if not already done):"
echo "   chmod +x power_monitor_script.py"
echo "   Run your script:"
echo "   python3 ./power_monitor_script.py"
echo "--------------------------------------------------------------------"
echo
echo ">>> The script has finished. Please follow the 'NEXT STEPS' above. <<<"
