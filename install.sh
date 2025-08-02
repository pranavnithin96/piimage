#!/bin/bash
echo "🚀 PowerMonitor Complete Installation"
echo "===================================="

# Copy the enhanced setup to current directory if needed
if [ -f "src/turnkey_setup_interactive.py" ]; then
    echo "✅ turnkey_setup_interactive.py found"
    cp src/turnkey_setup_interactive.py enhanced_turnkey_setup.py
else
    echo "❌ turnkey_setup_interactive.py not found!"
    echo "Please check that you have the complete repository."
    exit 1
fi

# Run the deployment script
echo "🔧 Running deployment script..."
./scripts/deploy_enhanced.sh

echo ""
echo "✅ Installation complete!"
echo "🔌 Your PowerMonitor system is now ready!"
echo ""
echo "📋 What was installed:"
echo "  • Interactive setup framework"
echo "  • Professional SSH interface"
echo "  • Real-time monitoring engine"
echo "  • Complete configuration system"
echo ""
echo "🚀 Next: SSH into this Pi and the setup wizard will run automatically!"
