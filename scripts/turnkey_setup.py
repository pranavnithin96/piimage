#!/usr/bin/env python3

import curses
import subprocess
import json
import time
import sys
import os
import uuid
from datetime import datetime

class PowerMonitorSetup:
    def __init__(self):
        self.config_file = "/etc/powermonitor/config.conf"
        self.setup_complete_file = "/opt/powermonitor/.setup_complete"
        self.service_name = "powermonitor"
        self.config = {}
        
    def is_first_time_setup(self):
        """Check if this is the first time running setup"""
        return not os.path.exists(self.setup_complete_file)
    
    def generate_unique_device_id(self):
        """Generate unique device ID based on Pi hardware"""
        try:
            # Try to get Pi serial number
            with open('/proc/cpuinfo', 'r') as f:
                for line in f:
                    if line.startswith('Serial'):
                        serial = line.split(':')[1].strip()
                        return f"powermon_{serial}"
        except:
            pass
        
        try:
            # Fallback to MAC address
            result = subprocess.run(['cat', '/sys/class/net/eth0/address'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                mac = result.stdout.strip().replace(':', '')
                return f"powermon_{mac}"
        except:
            pass
        
        # Final fallback to UUID
        return f"powermon_{str(uuid.uuid4())[:8]}"
    
    def get_wifi_status(self):
        """Get current WiFi connection status"""
        try:
            result = subprocess.run(['iwgetid', '-r'], capture_output=True, text=True)
            if result.returncode == 0 and result.stdout.strip():
                return f"Connected to: {result.stdout.strip()}"
            else:
                return "Not connected to WiFi"
        except:
            return "WiFi status unknown"
    
    def scan_wifi(self):
        """Scan for available WiFi networks"""
        try:
            subprocess.run(['sudo', 'nmcli', 'device', 'wifi', 'rescan'], 
                         capture_output=True, timeout=10)
            result = subprocess.run(['nmcli', '-f', 'SSID,SIGNAL', 
                                   'device', 'wifi', 'list'], 
                                  capture_output=True, text=True, timeout=10)
            
            networks = []
            lines = result.stdout.strip().split('\n')[1:]  # Skip header
            for line in lines:
                parts = line.split()
                if len(parts) >= 2:
                    ssid = ' '.join(parts[:-1])  # Join all but last part (signal)
                    if ssid and ssid != '--' and len(ssid.strip()) > 0:
                        networks.append(ssid.strip())
            
            return list(set(networks))[:15]  # Return unique networks, max 15
        except:
            return []
    
    def connect_wifi(self, ssid, password):
        """Connect to WiFi network"""
        try:
            cmd = ['sudo', 'nmcli', 'device', 'wifi', 'connect', ssid, 'password', password]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                return True, "Successfully connected to WiFi!"
            else:
                return False, f"Connection failed: {result.stderr}"
        except subprocess.TimeoutExpired:
            return False, "Connection timeout - check password and try again"
        except Exception as e:
            return False, f"Error: {str(e)}"
    
    def save_config(self, config):
        """Save configuration to file"""
        try:
            # Create config directory with sudo
            subprocess.run(['sudo', 'mkdir', '-p', os.path.dirname(self.config_file)], check=True)
            
            # Write config to temporary file first
            temp_config = "/tmp/powermonitor_config.conf"
            with open(temp_config, 'w') as f:
                f.write("# Power Monitor Configuration - Auto-generated\n")
                f.write(f"# Setup completed: {datetime.now().isoformat()}\n")
                f.write("#\n")
                for key, value in config.items():
                    f.write(f"{key}={value}\n")
            
            # Copy to system location with sudo
            subprocess.run(['sudo', 'cp', temp_config, self.config_file], check=True)
            subprocess.run(['sudo', 'chown', 'pi:pi', self.config_file], check=True)
            
            # Clean up temp file
            os.remove(temp_config)
            
            return True, "Configuration saved successfully!"
        except Exception as e:
            return False, f"Error saving config: {str(e)}"
    
    def create_power_monitor_script(self, config):
        """Create the power monitor script with user's configuration"""
        script_content = f'''#!/usr/bin/env python3

import spidev
import time
import requests
import json
import math
import signal
import sys
from datetime import datetime, timezone

# Configuration - Auto-generated from setup
GRID_VOLTAGE = {config['VOLTAGE']}
SERVER_URL = "{config['SERVER_URL']}"
DEVICE_ID = "{config['DEVICE_ID']}"
LOCATION_NAME = "{config['LOCATION_NAME']}"
SEND_INTERVAL = 10

# CT Configuration
CT_CHANNELS = {{
    1: 0, 2: 1, 3: 2, 4: 3, 5: 4, 6: 5
}}

# CT Settings - All CTs have same rating as selected by user
CT_RATING = {config['CT_RATING']}
CT_BURDEN_RESISTOR = 18.0
CT_CALIBRATION = 1.0
CT_REVERSED = True
DEFAULT_CALIBRATION = 0.88

# Hardware configuration
FREQUENCY = 60
ADC_BITS = 1024
NUM_SAMPLES = 500

# Global variables
spi = None
running = True

def signal_handler(sig, frame):
    global running
    log_message("Received shutdown signal, stopping service...")
    running = False
    if spi:
        spi.close()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def log_message(message):
    """Log message with timestamp"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{{timestamp}}] {{message}}")
    sys.stdout.flush()

def init_spi():
    global spi
    try:
        spi = spidev.SpiDev()
        spi.open(0, 0)
        spi.max_speed_hz = 500000
        log_message("✅ SPI initialized successfully")
        return True
    except Exception as e:
        log_message(f"❌ SPI initialization failed: {{e}}")
        return False

def read_adc(channel):
    """Read single value from ADC channel"""
    if channel < 0 or channel > 7:
        return -1
    try:
        adc = spi.xfer2([1, (8 + channel) << 4, 0])
        data = ((adc[1] & 3) << 8) + adc[2]
        return data
    except Exception as e:
        return -1

def collect_all_ct_samples(num_samples):
    """Collect samples from all 6 CT sensors simultaneously"""
    ct_samples = {{ct_num: [] for ct_num in CT_CHANNELS.keys()}}
    sample_interval = (8.0 / FREQUENCY) / num_samples

    start_time = time.time()
    for i in range(num_samples):
        for ct_num, channel in CT_CHANNELS.items():
            ct_reading = read_adc(channel)
            if ct_reading >= 0:
                ct_samples[ct_num].append(ct_reading)

        elapsed = time.time() - start_time
        expected = (i + 1) * sample_interval
        if expected > elapsed:
            time.sleep(expected - elapsed)

    return ct_samples

def calculate_power_for_ct(current_samples, ct_num):
    """Calculate power for a single CT sensor"""
    
    if not current_samples or len(current_samples) < 100:
        return None

    num_samples = len(current_samples)
    
    # Board voltage reference (3.3V)
    board_voltage = 3.31
    vref = board_voltage / ADC_BITS
    
    # CT scaling based on user-selected CT rating
    if CT_RATING == 30:
        volts_per_amp = 1.0 / 30  # 30A:1V
    elif CT_RATING == 50:
        volts_per_amp = 1.0 / 50  # 50A:1V  
    elif CT_RATING == 100:
        volts_per_amp = 0.9 / 100  # 100A:0.9V (SCT-T16)
    elif CT_RATING == 200:
        volts_per_amp = 1.0 / 200  # 200A:1V
    else:
        volts_per_amp = 1.0 / CT_RATING  # Generic scaling
    
    current_scaling = (vref * CT_CALIBRATION * DEFAULT_CALIBRATION) / volts_per_amp
    
    # Process current samples
    sum_squares = 0
    sum_values = 0
    
    for sample in current_samples:
        sum_squares += sample * sample
        sum_values += sample
    
    # Calculate RMS current
    avg_raw = sum_values / num_samples
    mean_square = sum_squares / num_samples
    current_rms = math.sqrt(max(0, mean_square - (avg_raw * avg_raw))) * current_scaling
    
    # Debug info
    variation = max(current_samples) - min(current_samples)
    
    # Power calculation
    voltage_fixed = GRID_VOLTAGE
    power_factor = 0.90
    power_calculated = voltage_fixed * abs(current_rms) * power_factor
    
    # Handle CT reversal
    final_current = current_rms
    final_power = power_calculated
    
    if CT_REVERSED:
        if final_power < 0:
            final_power = abs(final_power)
        else:
            final_current = -abs(final_current)
    
    # Apply 1W threshold
    if abs(final_power) < 1.0:
        final_power = 0.0
    
    # Calculate apparent power and power factor
    apparent = voltage_fixed * abs(final_current)
    pf = power_factor if apparent > 0.1 else 0.0
    
    return {{
        'power': abs(final_power),
        'current': abs(final_current), 
        'voltage': voltage_fixed,
        'pf': pf,
        'variation': variation
    }}

def calculate_all_ct_power(all_ct_samples):
    """Calculate power for all CT sensors"""
    ct_results = {{}}
    
    for ct_num in CT_CHANNELS.keys():
        if ct_num in all_ct_samples:
            result = calculate_power_for_ct(all_ct_samples[ct_num], ct_num)
            ct_results[ct_num] = result
        else:
            ct_results[ct_num] = None
    
    return ct_results

def send_to_server(data):
    """Send data to server with error handling"""
    try:
        response = requests.post(SERVER_URL, json=data, timeout=10)
        if response.status_code == 200:
            return True, "Success"
        else:
            return False, f"HTTP {{response.status_code}}"
    except requests.exceptions.Timeout:
        return False, "Timeout"
    except requests.exceptions.ConnectionError:
        return False, "Connection failed"
    except Exception as e:
        return False, f"Error: {{str(e)[:50]}}"

def format_ct_results_for_log(ct_results):
    """Format CT results for readable logging"""
    active_cts = []
    total_power = 0
    
    for ct_num, result in ct_results.items():
        if result and result['power'] > 0:
            power = result['power']
            current = result['current']
            variation = result['variation']
            total_power += power
            active_cts.append(f"CT{{ct_num}}:{{power:.1f}}W/{{current:.3f}}A")
    
    if active_cts:
        return f"Total:{{total_power:.1f}}W | " + " | ".join(active_cts)
    else:
        return "No active loads detected"

def main():
    log_message(f"🔌 Power Monitor Starting - {{LOCATION_NAME}}")
    log_message("=" * 60)
    log_message(f"Device ID: {{DEVICE_ID}}")
    log_message(f"Location: {{LOCATION_NAME}}")
    log_message(f"Voltage: {{GRID_VOLTAGE}}V")
    log_message(f"CT Rating: {{CT_RATING}}A (all CTs)")
    log_message(f"Server: {{SERVER_URL}}")
    log_message("=" * 60)

    if not init_spi():
        log_message("❌ Cannot start without SPI. Check hardware connections.")
        return

    successful_readings = 0
    failed_readings = 0
    successful_uploads = 0
    failed_uploads = 0

    log_message(f"🚀 Service started - monitoring 6x{{CT_RATING}}A CT sensors")

    while running:
        try:
            all_ct_samples = collect_all_ct_samples(NUM_SAMPLES)
            ct_results = calculate_all_ct_power(all_ct_samples)
            
            if any(result is not None for result in ct_results.values()):
                successful_readings += 1
                
                # Create payload
                payload = {{
                    "device_id": DEVICE_ID,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "location": LOCATION_NAME,
                    "readings": {{
                        "cts": {{}},
                        "voltage_rms": round(GRID_VOLTAGE, 1)
                    }}
                }}
                
                # Add each CT's data
                for ct_num in range(1, 7):
                    result = ct_results.get(ct_num)
                    if result:
                        payload["readings"]["cts"][f"ct_{{ct_num}}"] = {{
                            "real_power_w": round(result['power'], 1),
                            "amps": round(result['current'], 3),
                            "pf": round(result['pf'], 3)
                        }}
                    else:
                        payload["readings"]["cts"][f"ct_{{ct_num}}"] = {{
                            "real_power_w": 0.0,
                            "amps": 0.0,
                            "pf": 0.0
                        }}
                
                # Send to server
                success, message = send_to_server(payload)
                
                if success:
                    successful_uploads += 1
                    status = "✅"
                else:
                    failed_uploads += 1
                    status = "❌"
                
                log_line = format_ct_results_for_log(ct_results)
                log_message(f"{{status}} {{log_line}} | {{message}}")
                
            else:
                failed_readings += 1
                log_message("❌ No valid readings from any CT sensor")
                
            time.sleep(SEND_INTERVAL)
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            failed_readings += 1
            log_message(f"❌ Error: {{e}}")
            time.sleep(5)

    log_message("🛑 Power Monitor Service Stopped")

if __name__ == "__main__":
    main()
'''
        
        # Write the script using sudo
        try:
            # Create directory with sudo
            subprocess.run(['sudo', 'mkdir', '-p', '/opt/powermonitor'], check=True)
            
            # Write to temp file first
            temp_script = "/tmp/pi_monitor_script.py"
            with open(temp_script, 'w') as f:
                f.write(script_content)
            
            # Copy to system location with sudo
            subprocess.run(['sudo', 'cp', temp_script, '/opt/powermonitor/pi_monitor_script.py'], check=True)
            subprocess.run(['sudo', 'chmod', '+x', '/opt/powermonitor/pi_monitor_script.py'], check=True)
            subprocess.run(['sudo', 'chown', 'pi:pi', '/opt/powermonitor/pi_monitor_script.py'], check=True)
            
            # Clean up temp file
            os.remove(temp_script)
            
            return True, "Power monitor script created successfully!"
        except Exception as e:
            return False, f"Error creating script: {str(e)}"
    
    def install_service(self):
        """Install the systemd service"""
        service_content = '''[Unit]
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
'''
        
        try:
            # Write service file to temp location
            temp_service = '/tmp/powermonitor.service'
            with open(temp_service, 'w') as f:
                f.write(service_content)
            
            # Copy to system location with sudo
            subprocess.run(['sudo', 'cp', temp_service, '/etc/systemd/system/powermonitor.service'], check=True)
            subprocess.run(['sudo', 'systemctl', 'daemon-reload'], check=True)
            subprocess.run(['sudo', 'systemctl', 'enable', 'powermonitor'], check=True)
            
            # Clean up temp file
            os.remove(temp_service)
            
            return True, "Service installed and enabled!"
        except Exception as e:
            return False, f"Error installing service: {str(e)}"
    
    def mark_setup_complete(self):
        """Mark setup as complete"""
        try:
            # Create directory with sudo
            subprocess.run(['sudo', 'mkdir', '-p', os.path.dirname(self.setup_complete_file)], check=True)
            
            # Write to temp file first
            temp_file = "/tmp/setup_complete"
            with open(temp_file, 'w') as f:
                f.write(f"Setup completed: {datetime.now().isoformat()}\n")
            
            # Copy to system location with sudo
            subprocess.run(['sudo', 'cp', temp_file, self.setup_complete_file], check=True)
            subprocess.run(['sudo', 'chown', 'pi:pi', self.setup_complete_file], check=True)
            
            # Clean up temp file
            os.remove(temp_file)
            
            return True
        except Exception as e:
            print(f"Warning: Could not mark setup complete: {e}")
            return False

def draw_header(stdscr, title):
    """Draw the application header"""
    height, width = stdscr.getmaxyx()
    
    stdscr.addstr(0, (width - len(title)) // 2, title, curses.A_BOLD)
    stdscr.addstr(1, (width - 40) // 2, f"⚡ Setup Time: {datetime.now().strftime('%H:%M:%S')}")
    stdscr.addstr(2, 0, "=" * width)

def show_message(stdscr, message, wait_time=3):
    """Show a message and wait"""
    height, width = stdscr.getmaxyx()
    
    for i in range(height - 5, height - 1):
        stdscr.addstr(i, 0, " " * width)
    
    lines = message.split('\n')
    for i, line in enumerate(lines):
        if i < 4:  # Max 4 lines
            stdscr.addstr(height - 4 + i, 2, line[:width-4])
    
    stdscr.addstr(height - 1, 2, f"Please wait {wait_time} seconds..." if wait_time > 0 else "Press any key to continue...")
    stdscr.refresh()
    
    if wait_time > 0:
        time.sleep(wait_time)
    else:
        stdscr.getch()

def wifi_setup_screen(stdscr, setup):
    """WiFi setup screen"""
    while True:
        stdscr.clear()
        draw_header(stdscr, "🔌 Power Monitor Setup - WiFi Configuration")
        
        wifi_status = setup.get_wifi_status()
        stdscr.addstr(4, 2, f"Current Status: {wifi_status}")
        
        # Check if already connected
        if "Connected to:" in wifi_status:
            stdscr.addstr(6, 2, "✅ WiFi is already connected!")
            stdscr.addstr(7, 2, "Press ENTER to continue to device configuration...")
            stdscr.refresh()
            key = stdscr.getch()
            if key == ord('\n') or key == ord('\r'):
                return True
            continue
        
        stdscr.addstr(6, 2, "WiFi Setup Options:", curses.A_BOLD)
        options = ["📡 Scan & Connect to Network", "📝 Manual WiFi Entry", "⏭️  Skip (Use Ethernet)"]
        
        for idx, option in enumerate(options):
            stdscr.addstr(8 + idx, 4, f"{idx + 1}. {option}")
        
        stdscr.addstr(12, 2, "Select option (1-3): ")
        stdscr.refresh()
        
        key = stdscr.getch()
        if key == ord('1'):
            if scan_and_connect_wifi(stdscr, setup):
                return True
        elif key == ord('2'):
            if manual_wifi_entry(stdscr, setup):
                return True
        elif key == ord('3'):
            return True  # Skip WiFi setup

def scan_and_connect_wifi(stdscr, setup):
    """Scan and connect to WiFi"""
    stdscr.clear()
    draw_header(stdscr, "🔌 WiFi Setup - Scanning Networks")
    stdscr.addstr(4, 2, "Scanning for WiFi networks... Please wait...")
    stdscr.refresh()
    
    networks = setup.scan_wifi()
    
    if not networks:
        show_message(stdscr, "❌ No networks found!\nTry manual entry or check WiFi adapter.", 0)
        return False
    
    while True:
        stdscr.clear()
        draw_header(stdscr, "🔌 WiFi Setup - Select Network")
        stdscr.addstr(4, 2, "Available Networks:", curses.A_BOLD)
        
        # Show networks
        max_show = min(10, len(networks))
        for idx in range(max_show):
            stdscr.addstr(6 + idx, 4, f"{idx + 1:2d}. {networks[idx]}")
        
        if len(networks) > 10:
            stdscr.addstr(6 + max_show, 4, f"... and {len(networks) - 10} more")
        
        stdscr.addstr(6 + max_show + 2, 2, "Enter network number (or 'r' to rescan, 'b' for back): ")
        stdscr.refresh()
        
        curses.echo()
        choice = stdscr.getstr().decode('utf-8').strip().lower()
        curses.noecho()
        
        if choice == 'r':
            return scan_and_connect_wifi(stdscr, setup)  # Rescan
        elif choice == 'b':
            return False
        
        try:
            network_idx = int(choice) - 1
            if 0 <= network_idx < len(networks):
                selected_network = networks[network_idx]
                
                # Get password
                stdscr.addstr(6 + max_show + 4, 2, f"Password for '{selected_network}': ")
                stdscr.refresh()
                
                curses.echo()
                password = stdscr.getstr().decode('utf-8')
                curses.noecho()
                
                # Connect
                stdscr.addstr(6 + max_show + 6, 2, "Connecting... Please wait...")
                stdscr.refresh()
                
                success, message = setup.connect_wifi(selected_network, password)
                show_message(stdscr, f"{'✅' if success else '❌'} {message}", 3)
                
                if success:
                    return True
            else:
                show_message(stdscr, "❌ Invalid selection!", 2)
        except ValueError:
            show_message(stdscr, "❌ Please enter a valid number!", 2)

def manual_wifi_entry(stdscr, setup):
    """Manual WiFi entry"""
    stdscr.clear()
    draw_header(stdscr, "🔌 WiFi Setup - Manual Entry")
    
    stdscr.addstr(4, 2, "Manual WiFi Configuration", curses.A_BOLD)
    stdscr.addstr(6, 2, "Network Name (SSID): ")
    stdscr.refresh()
    
    curses.echo()
    ssid = stdscr.getstr(6, 23).decode('utf-8').strip()
    
    if not ssid:
        curses.noecho()
        show_message(stdscr, "❌ Network name cannot be empty!", 2)
        return False
    
    stdscr.addstr(7, 2, "Password: ")
    stdscr.refresh()
    password = stdscr.getstr(7, 12).decode('utf-8')
    curses.noecho()
    
    stdscr.addstr(9, 2, "Connecting... Please wait...")
    stdscr.refresh()
    
    success, message = setup.connect_wifi(ssid, password)
    show_message(stdscr, f"{'✅' if success else '❌'} {message}", 3)
    return success

def device_configuration_screen(stdscr, setup):
    """Device configuration screen"""
    config = {
        'DEVICE_ID': setup.generate_unique_device_id(),
        'LOCATION_NAME': '',
        'CT_RATING': 100,
        'VOLTAGE': 120.0,
        'SERVER_URL': 'https://linesights.com/api/data'
    }
    
    current_field = 0
    fields = ['LOCATION_NAME', 'CT_RATING', 'VOLTAGE', 'SERVER_URL']
    
    ct_options = [30, 50, 100, 200]
    voltage_options = [110.0, 120.0, 230.0, 240.0]
    
    while True:
        stdscr.clear()
        draw_header(stdscr, "🔌 Power Monitor Setup - Device Configuration")
        
        stdscr.addstr(4, 2, f"Device ID: {config['DEVICE_ID']} (auto-generated)", curses.A_DIM)
        
        # Location Name
        attr = curses.A_REVERSE if current_field == 0 else curses.A_NORMAL
        stdscr.addstr(6, 2, "Location Name: ", attr)
        stdscr.addstr(6, 17, config['LOCATION_NAME'] or "[Enter location name]", attr)
        
        # CT Rating
        attr = curses.A_REVERSE if current_field == 1 else curses.A_NORMAL
        stdscr.addstr(8, 2, "CT Sensor Rating: ", attr)
        ct_display = f"{config['CT_RATING']}A (Use ←→ to change)"
        stdscr.addstr(8, 20, ct_display, attr)
        
        # Voltage
        attr = curses.A_REVERSE if current_field == 2 else curses.A_NORMAL
        stdscr.addstr(10, 2, "Grid Voltage: ", attr)
        voltage_display = f"{config['VOLTAGE']:.0f}V (Use ←→ to change)"
        stdscr.addstr(10, 16, voltage_display, attr)
        
        # Server URL
        attr = curses.A_REVERSE if current_field == 3 else curses.A_NORMAL
        stdscr.addstr(12, 2, "Server URL: ", attr)
        stdscr.addstr(12, 14, config['SERVER_URL'], attr)
        
        # Instructions
        stdscr.addstr(15, 2, "Navigation:", curses.A_BOLD)
        stdscr.addstr(16, 2, "↑↓ - Select field  |  ENTER - Edit  |  ←→ - Change options  |  F1 - Finish Setup")
        
        # CT Rating info
        stdscr.addstr(18, 2, "CT Rating Guide:", curses.A_BOLD)
        stdscr.addstr(19, 2, "30A: Individual circuits (15-20A breakers)")
        stdscr.addstr(20, 2, "100A: Large appliances, sub-panels")
        stdscr.addstr(21, 2, "200A: Main service entrance")
        
        stdscr.refresh()
        
        key = stdscr.getch()
        
        if key == curses.KEY_UP and current_field > 0:
            current_field -= 1
        elif key == curses.KEY_DOWN and current_field < len(fields) - 1:
            current_field += 1
        elif key == curses.KEY_LEFT:
            if current_field == 1:  # CT Rating
                current_idx = ct_options.index(config['CT_RATING'])
                config['CT_RATING'] = ct_options[(current_idx - 1) % len(ct_options)]
            elif current_field == 2:  # Voltage
                current_idx = voltage_options.index(config['VOLTAGE'])
                config['VOLTAGE'] = voltage_options[(current_idx - 1) % len(voltage_options)]
        elif key == curses.KEY_RIGHT:
            if current_field == 1:  # CT Rating
                current_idx = ct_options.index(config['CT_RATING'])
                config['CT_RATING'] = ct_options[(current_idx + 1) % len(ct_options)]
            elif current_field == 2:  # Voltage
                current_idx = voltage_options.index(config['VOLTAGE'])
                config['VOLTAGE'] = voltage_options[(current_idx + 1) % len(voltage_options)]
        elif key == ord('\n') or key == ord('\r'):
            if current_field == 0:  # Location Name
                stdscr.addstr(23, 2, "Enter location name: ")
                stdscr.refresh()
                curses.echo()
                location = stdscr.getstr().decode('utf-8').strip()
                curses.noecho()
                if location:
                    config['LOCATION_NAME'] = location
            elif current_field == 3:  # Server URL
                stdscr.addstr(23, 2, "Enter server URL: ")
                stdscr.refresh()
                curses.echo()
                url = stdscr.getstr().decode('utf-8').strip()
                curses.noecho()
                if url:
                    config['SERVER_URL'] = url
        elif key == 265:  # F1
            if config['LOCATION_NAME']:
                return config
            else:
                show_message(stdscr, "❌ Please enter a location name before finishing!", 2)

def final_setup_screen(stdscr, setup, config):
    """Final setup and installation screen"""
    stdscr.clear()
    draw_header(stdscr, "🔌 Power Monitor Setup - Final Installation")
    
    stdscr.addstr(4, 2, "Configuration Summary:", curses.A_BOLD)
    stdscr.addstr(6, 4, f"Device ID: {config['DEVICE_ID']}")
    stdscr.addstr(7, 4, f"Location: {config['LOCATION_NAME']}")
    stdscr.addstr(8, 4, f"CT Rating: {config['CT_RATING']}A (all 6 sensors)")
    stdscr.addstr(9, 4, f"Grid Voltage: {config['VOLTAGE']:.0f}V")
    stdscr.addstr(10, 4, f"Server URL: {config['SERVER_URL']}")
    
    stdscr.addstr(12, 2, "Press ENTER to install and start monitoring, ESC to go back...")
    stdscr.refresh()
    
    key = stdscr.getch()
    if key == 27:  # ESC
        return False
    elif key == ord('\n') or key == ord('\r'):
        # Start installation
        stdscr.addstr(14, 2, "Installing Power Monitor Service...")
        stdscr.refresh()
        
        # Save config
        success, message = setup.save_config(config)
        if not success:
            show_message(stdscr, f"❌ {message}", 0)
            return False
        
        stdscr.addstr(15, 2, "✅ Configuration saved")
        stdscr.refresh()
        
        # Create power monitor script
        success, message = setup.create_power_monitor_script(config)
        if not success:
            show_message(stdscr, f"❌ {message}", 0)
            return False
        
        stdscr.addstr(16, 2, "✅ Power monitor script created")
        stdscr.refresh()
        
        # Install service
        success, message = setup.install_service()
        if not success:
            show_message(stdscr, f"❌ {message}", 0)
            return False
        
        stdscr.addstr(17, 2, "✅ Service installed and enabled")
        stdscr.refresh()
        
        # Mark setup complete
        setup.mark_setup_complete()
        stdscr.addstr(18, 2, "✅ Setup marked as complete")
        stdscr.refresh()
        
        # Start service
        try:
            subprocess.run(['sudo', 'systemctl', 'start', 'powermonitor'])
            stdscr.addstr(19, 2, "✅ Service started successfully!")
        except:
            stdscr.addstr(19, 2, "⚠️  Service installed but failed to start")
        
        stdscr.refresh()
        
        stdscr.addstr(21, 2, "🎉 Setup Complete!", curses.A_BOLD)
        stdscr.addstr(22, 2, f"Your power monitor is now running at: {config['LOCATION_NAME']}")
        stdscr.addstr(23, 2, "Monitor status with: journalctl -u powermonitor -f")
        stdscr.addstr(24, 2, "Press any key to exit...")
        stdscr.refresh()
        stdscr.getch()
        
        return True

def main_setup_flow(stdscr):
    """Main setup flow"""
    curses.curs_set(0)  # Hide cursor
    
    setup = PowerMonitorSetup()
    
    # Check if this is first time setup
    if not setup.is_first_time_setup():
        stdscr.clear()
        draw_header(stdscr, "🔌 Power Monitor - Already Configured")
        stdscr.addstr(4, 2, "This device has already been configured.")
        stdscr.addstr(5, 2, "The power monitor service should be running.")
        stdscr.addstr(7, 2, "To reconfigure, delete: /opt/powermonitor/.setup_complete")
        stdscr.addstr(8, 2, "To check status: journalctl -u powermonitor -f")
        stdscr.addstr(10, 2, "Press any key to exit...")
        stdscr.refresh()
        stdscr.getch()
        return
    
    # Welcome screen
    stdscr.clear()
    draw_header(stdscr, "🔌 Welcome to Power Monitor Setup")
    stdscr.addstr(4, 2, "This wizard will configure your power monitoring device.")
    stdscr.addstr(6, 2, "Steps:")
    stdscr.addstr(7, 4, "1. Connect to WiFi")
    stdscr.addstr(8, 4, "2. Configure device settings")
    stdscr.addstr(9, 4, "3. Install and start monitoring")
    stdscr.addstr(11, 2, "Press ENTER to begin setup...")
    stdscr.refresh()
    
    key = stdscr.getch()
    if key != ord('\n') and key != ord('\r'):
        return
    
    # WiFi Setup
    if not wifi_setup_screen(stdscr, setup):
        return
    
    # Device Configuration
    config = device_configuration_screen(stdscr, setup)
    if not config:
        return
    
    # Final Setup
    final_setup_screen(stdscr, setup, config)

def main():
    """Main application entry point"""
    try:
        curses.wrapper(main_setup_flow)
    except KeyboardInterrupt:
        print("\nSetup cancelled.")
    except Exception as e:
        print(f"Setup error: {e}")

if __name__ == "__main__":
    main()
