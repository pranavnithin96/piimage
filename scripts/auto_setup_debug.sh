sudo tee /opt/powermonitor/auto_setup_debug.sh > /dev/null << 'EOF'
#!/bin/bash

echo "=== AUTO-SETUP DEBUG START ==="
echo "SSH_CONNECTION: '$SSH_CONNECTION'"
echo "Shell options: '$-'"
echo "Setup complete file exists: $(test -f /opt/powermonitor/.setup_complete && echo YES || echo NO)"

# Test the exact conditions
SSH_TEST=$([[ -n "$SSH_CONNECTION" ]] && echo "PASS" || echo "FAIL")
INTERACTIVE_TEST=$([[ $- == *i* ]] && echo "PASS" || echo "FAIL")

echo "SSH_CONNECTION test: $SSH_TEST"
echo "Interactive shell test: $INTERACTIVE_TEST"

# Enhanced Auto-run setup script on SSH login
if [[ -n "$SSH_CONNECTION" ]] && [[ $- == *i* ]]; then
    echo "✅ Both conditions MET - checking setup status"
    
    # Check if setup is complete
    if [ ! -f "/opt/powermonitor/.setup_complete" ]; then
        echo "✅ Setup file NOT found - launching wizard"
        echo ""
        echo "🔌 Welcome to Enhanced Power Monitor!"
        echo "Features: Custom device names + Automatic timezone detection"
        echo "Starting configuration wizard..."
        echo ""
        python3 /opt/powermonitor/turnkey_setup.py
        
        # If setup completed successfully, show success message
        if [ -f "/opt/powermonitor/.setup_complete" ]; then
            echo ""
            echo "🎉 Power Monitor is now configured and running!"
            echo "Monitor with: journalctl -u powermonitor -f"
            echo ""
        fi
    else
        echo "ℹ️  Setup file found - showing status instead"
        # Setup already complete, show status
        echo ""
        echo "🔌 Enhanced Power Monitor Status:"
        
        # Show device info from config
        if [ -f "/etc/powermonitor/config.conf" ]; then
            DEVICE_ID=$(grep "DEVICE_ID=" /etc/powermonitor/config.conf 2>/dev/null | cut -d'=' -f2)
            LOCATION=$(grep "LOCATION_NAME=" /etc/powermonitor/config.conf 2>/dev/null | cut -d'=' -f2)
            TIMEZONE=$(grep "TIMEZONE=" /etc/powermonitor/config.conf 2>/dev/null | cut -d'=' -f2)
            echo "📱 Device: $DEVICE_ID"
            echo "📍 Location: $LOCATION"
            echo "🕐 Timezone: $TIMEZONE"
        fi
        
        # Check service status
        if systemctl is-active --quiet powermonitor 2>/dev/null; then
            echo "✅ Service is running"
            echo "📊 Monitor logs: journalctl -u powermonitor -f"
        else
            echo "❌ Service is not running"
            echo "🔧 Start with: sudo systemctl start powermonitor"
        fi
        echo ""
    fi
else
    echo "❌ Conditions NOT met:"
    echo "   SSH_CONNECTION empty: $([[ -z "$SSH_CONNECTION" ]] && echo YES || echo NO)"
    echo "   Non-interactive shell: $([[ $- != *i* ]] && echo YES || echo NO)"
fi

echo "=== AUTO-SETUP DEBUG END ==="
EOF
