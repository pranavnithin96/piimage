#!/bin/bash

echo "Power Monitor Service Status"
echo "============================"

# Check if service exists
if ! systemctl list-unit-files | grep -q "powermonitor.service"; then
    echo "ERROR: Power Monitor service not installed"
    echo "Run: ./setup_service.sh"
    exit 1
fi

# Get service status
STATUS=$(systemctl is-active powermonitor)
ENABLED=$(systemctl is-enabled powermonitor)

echo "Service Status: $STATUS"
echo "Auto-start: $ENABLED"
echo ""

# Show status
case $STATUS in
    "active")
        echo "Service is RUNNING"
        ;;
    "inactive")
        echo "Service is STOPPED"
        ;;
    "failed")
        echo "Service has FAILED"
        ;;
    *)
        echo "Service status: $STATUS"
        ;;
esac

echo ""
echo "Recent logs:"
journalctl -u powermonitor -n 5 --no-pager

echo ""
echo "Commands:"
echo "  sudo systemctl start powermonitor     # Start"
echo "  sudo systemctl stop powermonitor      # Stop"
echo "  sudo systemctl restart powermonitor   # Restart"
echo "  journalctl -u powermonitor -f         # Live logs"
