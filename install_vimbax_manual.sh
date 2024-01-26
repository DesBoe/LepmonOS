#!/bin/bash
# Manual VimbaX installation script for Lepmon
# Run this if VimbaX was not installed during image build

set -e

echo "=========================================="
echo "VimbaX SDK Manual Installation for Lepmon"
echo "=========================================="
echo ""

# Check if already installed
if [ -d /opt/VimbaX ] && [ -f /opt/VimbaX/api/lib/libVmbC.so ]; then
    echo "✓ VimbaX is already installed at /opt/VimbaX"
    echo ""
    echo "If you want to reinstall, run: sudo rm -rf /opt/VimbaX"
    echo "Then run this script again."
    exit 0
fi

# Check for sudo
if [ "$EUID" -ne 0 ]; then 
    echo "This script must be run as root (use sudo)"
    exit 1
fi

echo "Step 1/6: Downloading VimbaX SDK..."
cd /tmp
wget --show-progress \
    https://github.com/openUC2/ImSwitchDockerInstall/releases/download/imswitch-master/VimbaX_Setup-2025-1-Linux_ARM64.tar.gz

echo ""
echo "Step 2/6: Extracting archive..."
tar -xzf VimbaX_Setup-2025-1-Linux_ARM64.tar.gz -C /opt

# Find the actual extracted directory
EXTRACTED_DIR=$(find /opt -maxdepth 1 -type d -name "VimbaX*" | head -1)
if [ -z "$EXTRACTED_DIR" ]; then
    echo "✗ ERROR: Could not find extracted VimbaX directory!"
    ls -la /opt | grep -i vimba
    exit 1
fi

echo "Found extracted directory: $EXTRACTED_DIR"

# Rename to standard location if needed
if [ "$EXTRACTED_DIR" != "/opt/VimbaX" ]; then
    echo "Renaming $EXTRACTED_DIR to /opt/VimbaX"
    rm -rf /opt/VimbaX 2>/dev/null || true
    mv "$EXTRACTED_DIR" /opt/VimbaX
fi

rm VimbaX_Setup-2025-1-Linux_ARM64.tar.gz 2>/dev/null || true

# Verify directory structure
echo "Checking VimbaX directory structure..."
ls -la /opt/VimbaX/ | head -20

echo ""
echo "Step 3/6: Registering GenTL transport layer..."
cd /opt/VimbaX/cti
bash ./Install_GenTL_Path.sh

echo ""
echo "Step 4/6: Configuring environment variables..."
cat > /etc/profile.d/vimbax.sh <<'EOF'
export VIMBA_HOME="/opt/VimbaX"
export GENICAM_GENTL64_PATH="/opt/VimbaX/cti"
export LD_LIBRARY_PATH="${LD_LIBRARY_PATH:+${LD_LIBRARY_PATH}:}/opt/VimbaX/api/lib"
EOF

echo ""
echo "Step 5/6: Registering libraries with ldconfig..."
echo "/opt/VimbaX/api/lib" > /etc/ld.so.conf.d/vimbax.conf
ldconfig

echo ""
echo "Step 6/6: Installing VmbPy Python bindings..."
pip install --break-system-packages \
    "https://github.com/alliedvision/VmbPy/releases/download/1.2.1_beta1/vmbpy-1.2.1-py3-none-manylinux_2_27_aarch64.whl"

echo ""
echo "=========================================="
echo "Installation Complete!"
echo "=========================================="
echo ""
echo "Verifying installation..."

# Try to find libVmbC.so in various possible locations
VIMBA_LIB=""
for path in \
    /opt/VimbaX/api/lib/libVmbC.so \
    /opt/VimbaX/lib/libVmbC.so \
    /opt/VimbaX/VimbaC/DynamicLib/arm_64bit/libVmbC.so \
    $(find /opt/VimbaX -name "libVmbC.so" 2>/dev/null | head -1); do
    if [ -f "$path" ]; then
        VIMBA_LIB="$path"
        break
    fi
done

if [ -n "$VIMBA_LIB" ]; then
    echo "✓ libVmbC.so found at: $VIMBA_LIB"
    
    # Update environment to point to actual location
    LIB_DIR=$(dirname "$VIMBA_LIB")
    echo "Updating library path to: $LIB_DIR"
    
    cat > /etc/profile.d/vimbax.sh <<EOF
export VIMBA_HOME="/opt/VimbaX"
export GENICAM_GENTL64_PATH="/opt/VimbaX/cti"
export LD_LIBRARY_PATH="\${LD_LIBRARY_PATH:+\${LD_LIBRARY_PATH}:}$LIB_DIR"
EOF
    
    echo "$LIB_DIR" > /etc/ld.so.conf.d/vimbax.conf
    ldconfig
    
    echo "✓ Environment updated with correct library path"
else
    echo "✗ ERROR: libVmbC.so not found anywhere in /opt/VimbaX!"
    echo ""
    echo "Directory structure:"
    find /opt/VimbaX -type f -name "*.so" 2>/dev/null | head -20
    exit 1
fi

echo ""
echo "Testing Python import (you must load environment first)..."
echo "Run these commands to test:"
echo ""
echo "  source /etc/profile.d/vimbax.sh"
echo "  python3 -c \"from vmbpy import *; print('✓ VmbPy import OK')\""
echo ""
echo "To apply changes system-wide, either:"
echo "  1. Log out and log back in"
echo "  2. Reboot: sudo reboot"
echo ""
echo "Services will automatically pick up the environment on next start."
