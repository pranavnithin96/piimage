#!/bin/bash
echo "🚀 PowerMonitor Complete Installation"
echo "===================================="

# Copy the enhanced setup to current directory if needed
if [ ! -f "enhanced_turnkey_setup.py" ]; then
    echo "✅ enhanced_turnkey_setup.py already present"
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
