#!/usr/bin/env python3

import spidev
import time
import requests
import json
import math
import signal
import sys
from datetime import datetime, timezone

# Configuration
GRID_VOLTAGE = 120.0  # Standard US household voltage
FREQUENCY = 60

# ADC Configuration
VOLTAGE_CHANNEL = 5  # Not used in CT-only mode
CT_CHANNEL = 0       # CT1 on channel 0

# CT Configuration for SCT-T16 100A
CT_RATING = 100
CT_BURDEN_RESISTOR = 18.0
CT_CALIBRATION = 1.0
CT_REVERSED = True
DEFAULT_CALIBRATION = 0.88

# Server Configuration
SERVER_URL = "https://linesights.com/api/data"
DEVICE_ID = "rpipower_default_id"
SEND_INTERVAL = 10

# ADC settings
ADC_BITS = 1024
NUM_SAMPLES = 500

# Global variables
spi = None
running = True

def signal_handler(sig, frame):
    global running
    print("\nStopping power monitor...")
    running = False
    if spi:
        spi.close()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def init_spi():
    global spi
    spi = spidev.SpiDev()
    spi.open(0, 0)
    spi.max_speed_hz = 500000

def read_adc(channel):
    """Read single value from ADC channel"""
    if channel < 0 or channel > 7:
        return -1
    adc = spi.xfer2([1, (8 + channel) << 4, 0])
    data = ((adc[1] & 3) << 8) + adc[2]
    return data

def collect_current_samples(num_samples):
    """Collect current samples from CT"""
    current_samples = []
    sample_interval = (8.0 / FREQUENCY) / num_samples

    start_time = time.time()
    for i in range(num_samples):
        ct_reading = read_adc(CT_CHANNEL)
        current_samples.append(ct_reading)

        # Maintain timing
        elapsed = time.time() - start_time
        expected = (i + 1) * sample_interval
        if expected > elapsed:
            time.sleep(expected - elapsed)

    return current_samples

def calculate_power_from_current(current_samples):
    """Calculate power using CT-only with fixed voltage"""
    
    if not current_samples:
        return None

    num_samples = len(current_samples)
    
    # Board voltage reference (3.3V)
    board_voltage = 3.31
    vref = board_voltage / ADC_BITS
    
    # CT scaling: SCT-T16 100A:50mA with 18 ohm burden
    # At 100A: 50mA × 18Ω = 0.9V
    volts_per_amp = 0.9 / 100  # 0.009 V/A
    current_scaling = (vref * CT_CALIBRATION * DEFAULT_CALIBRATION) / volts_per_amp
    
    print(f"Debug: vref={vref:.6f}, current_scaling={current_scaling:.3f}")
    
    # Process current samples
    sum_squares = 0
    sum_values = 0
    
    for sample in current_samples:
        sum_squares += sample * sample
        sum_values += sample
    
    # Calculate RMS current
    avg_raw = sum_values / num_samples
    mean_square = sum_squares / num_samples
    current_rms = math.sqrt(mean_square - (avg_raw * avg_raw)) * current_scaling
    
    # Debug info
    variation = max(current_samples) - min(current_samples)
    print(f"Current ADC: min={min(current_samples)}, max={max(current_samples)}, variation={variation}")
    
    if variation < 5:
        print("⚠️  Warning: Low current variation - check CT connection")
    
    # Fixed voltage and power calculation
    voltage_fixed = GRID_VOLTAGE
    power_factor = 0.90
    power_calculated = voltage_fixed * abs(current_rms) * power_factor
    
    print(f"Power = {voltage_fixed}V × {abs(current_rms):.3f}A × {power_factor} = {power_calculated:.1f}W")
    
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
    
    print(f"Results: Power={abs(final_power):.1f}W, Current={abs(final_current):.3f}A, PF={pf:.3f}")
    
    return {
        'power': abs(final_power),
        'current': abs(final_current), 
        'voltage': voltage_fixed,
        'pf': pf
    }

def main():
    print("CT-Only Power Monitor")
    print("=" * 40)
    print(f"Fixed Voltage: {GRID_VOLTAGE}V")
    print(f"CT Channel: {CT_CHANNEL}")
    print(f"CT Rating: {CT_RATING}A")
    print(f"Power Factor: 0.90 (estimated)")
    print(f"Server: {SERVER_URL}")
    print("=" * 40)

    init_spi()
    time.sleep(1)

    while running:
        try:
            print(f"\n--- {datetime.now().strftime('%H:%M:%S')} ---")
            
            # Collect current samples
            samples = collect_current_samples(NUM_SAMPLES)
            
            # Calculate power
            results = calculate_power_from_current(samples)
            
            if results:
                power = results['power']
                current = results['current']
                voltage = results['voltage']
                pf = results['pf']
                
                print(f"📊 SENDING: {power:.1f}W, {current:.3f}A, {voltage:.1f}V, PF:{pf:.3f}")
                
                # Prepare server payload
                payload = {
                    "device_id": DEVICE_ID,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "readings": {
                        "cts": {
                            "ct_1": {"real_power_w": round(power, 1), "amps": round(current, 3), "pf": round(pf, 3)},
                            "ct_2": {"real_power_w": 0.0, "amps": 0.0, "pf": 0.0},
                            "ct_3": {"real_power_w": 0.0, "amps": 0.0, "pf": 0.0},
                            "ct_4": {"real_power_w": 0.0, "amps": 0.0, "pf": 0.0},
                            "ct_5": {"real_power_w": 0.0, "amps": 0.0, "pf": 0.0},
                            "ct_6": {"real_power_w": 0.0, "amps": 0.0, "pf": 0.0}
                        },
                        "voltage_rms": round(voltage, 1)
                    }
                }
                
                # Send to server
                try:
                    response = requests.post(SERVER_URL, json=payload, timeout=5)
                    print(f"Server response: {response.status_code}")
                    if response.status_code != 200:
                        print(f"Response: {response.text}")
                except Exception as e:
                    print(f"Error sending: {e}")
            else:
                print("No valid readings")
                
            time.sleep(SEND_INTERVAL)
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
