#!/usr/bin/env python3

import curses
import os

class PowerMonitorSetup:
    def __init__(self):
        self.config_file = "/etc/powermonitor/config.conf"
    
    def load_existing_config(self):
        """Load existing configuration if it exists"""
        config = {}
        
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    lines = f.readlines()
                
                for line in lines:
                    if '=' in line and not line.strip().startswith('#'):
                        key, value = line.strip().split('=', 1)
                        config[key] = value
                                
                return config, True  # True = existing config loaded
        except Exception as e:
            print(f"Error loading config: {e}")
        
        return {}, False  # False = no existing config

def main_setup_flow(stdscr):
    """Simple setup flow"""
    setup = PowerMonitorSetup()
    
    # Load existing configuration
    config, config_exists = setup.load_existing_config()
    
    stdscr.clear()
    if config_exists:
        stdscr.addstr(0, 2, "🔌 Current Power Monitor Configuration", curses.A_BOLD)
        stdscr.addstr(2, 2, "Current Settings:")
        
        row = 4
        for key, value in config.items():
            if not key.startswith('#'):
                stdscr.addstr(row, 4, f"{key}: {value}")
                row += 1
        
        stdscr.addstr(row + 2, 2, "Configuration loaded successfully!")
        stdscr.addstr(row + 3, 2, "Press any key to exit...")
    else:
        stdscr.addstr(0, 2, "🔌 No Configuration Found", curses.A_BOLD)
        stdscr.addstr(2, 2, "No existing configuration detected.")
        stdscr.addstr(3, 2, "Press any key to exit...")
    
    stdscr.refresh()
    stdscr.getch()

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
