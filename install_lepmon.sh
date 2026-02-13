#!/usr/bin/env bash
set -e

# ===========================================================================
# Lepmon OS Installation Script
# Runs inside aarch64 chroot during SD card image build
# ===========================================================================

export DEBIAN_FRONTEND=noninteractive
echo "nameserver 8.8.8.8" > /etc/resolv.conf
apt-get update

# ---------------------------------------------------------------------------
# System packages
# ---------------------------------------------------------------------------
apt-get install -y --no-install-recommends \
  python3 python3-pip python3-dev python3-venv \
  build-essential pkg-config \
  git curl wget \
  i2c-tools python3-smbus python3-gpiozero python3-rpi.gpio \
  libatlas-base-dev libopenblas-dev \
  python3-opencv python3-numpy python3-pil \
  libusb-1.0-0 libcap2-bin

# Networking / Access-Point
apt-get install -y --no-install-recommends \
  hostapd dnsmasq iptables-persistent wpasupplicant \
  rfkill iproute2 nftables python3-prctl

# SSH server (ensure it is present)
apt-get install -y --no-install-recommends openssh-server

# Free space immediately
apt-get clean
rm -rf /var/lib/apt/lists/*

# ---------------------------------------------------------------------------
# User / auto-login / SSH
# ---------------------------------------------------------------------------
if ! id Ento >/dev/null 2>&1; then
  useradd -m -s /bin/bash -G sudo,video,gpio,i2c,spi,dialout Ento
fi
echo "Ento:lepmon" | chpasswd

# Sudo without password (helpful in field)
echo "Ento ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/ento-nopasswd
chmod 440 /etc/sudoers.d/ento-nopasswd

# -- Auto-login on tty1 --
mkdir -p /etc/systemd/system/getty@tty1.service.d
cat > /etc/systemd/system/getty@tty1.service.d/autologin.conf <<'EOF'
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin Ento --noclear %I $TERM
EOF

# -- Auto-login on serial console --
mkdir -p /etc/systemd/system/serial-getty@ttyS0.service.d
cat > /etc/systemd/system/serial-getty@ttyS0.service.d/autologin.conf <<'EOF'
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin Ento --noclear %I 115200,38400,9600 vt102
EOF

# Disable first-boot user configuration wizards
systemctl disable userconfig.service 2>/dev/null || true
systemctl mask    userconfig.service 2>/dev/null || true
systemctl disable piwiz.service      2>/dev/null || true
systemctl mask    piwiz.service      2>/dev/null || true

# -- SSH: enable multiple ways to be safe --
systemctl enable ssh.service 2>/dev/null || true
touch /boot/firmware/ssh

# Bookworm userconf.txt so the image boots with Ento user
echo 'Ento:$6$rounds=656000$lepmonrandomsalt$gV8Q7nKxJrP2wM5L4fH9Y6t3R0uS1aZ8c4E7b2N5xW6vD3kF8jG1hI0mJ9oK2pL4qM6nO7rP8sQ9tU0wV1xY2zA' > /boot/firmware/userconf.txt

# ---------------------------------------------------------------------------
# Enable I2C, SPI and Serial (UART) in config.txt
# ---------------------------------------------------------------------------
CFG=/boot/firmware/config.txt

grep -q '^dtparam=i2c_arm=on'       "$CFG" || echo "dtparam=i2c_arm=on"       >> "$CFG"
grep -q '^dtparam=spi=on'           "$CFG" || echo "dtparam=spi=on"           >> "$CFG"
grep -q '^enable_uart=1'            "$CFG" || echo "enable_uart=1"            >> "$CFG"
grep -q '^dtoverlay=pwm-2chan'      "$CFG" || echo "dtoverlay=pwm-2chan"      >> "$CFG"
grep -q '^dtoverlay=i2c-rtc,ds3231' "$CFG" || echo "dtoverlay=i2c-rtc,ds3231" >> "$CFG"

grep -q '^i2c-dev' /etc/modules || echo "i2c-dev" >> /etc/modules
grep -q '^spi-dev' /etc/modules || echo "spi-dev" >> /etc/modules

# ---------------------------------------------------------------------------
# Lepmon application files (already copied by workflow)
# ---------------------------------------------------------------------------
mkdir -p /home/Ento/LepmonOS
chown -R Ento:Ento /home/Ento
chown -R Ento:Ento /home/Ento/LepmonOS
chmod +x /home/Ento/LepmonOS/*.sh 2>/dev/null || true
chmod +x /home/Ento/LepmonOS/*.py 2>/dev/null || true

# ---------------------------------------------------------------------------
# Python dependencies from requirements.txt
# ---------------------------------------------------------------------------
cd /home/Ento/LepmonOS || true

if [ -f requirements.txt ]; then
  pip install --break-system-packages -r requirements.txt || true
fi

# GitHub-hosted packages
pip install --break-system-packages \
  "https://github.com/alliedvision/VimbaPython/archive/refs/heads/master.zip" \
  "https://github.com/e71828/pi_ina226/archive/refs/heads/main.zip" \
  "https://github.com/openUC2/imswitchclient/archive/refs/heads/main.zip" \
  || true

# Install local wheel packages shipped in the repo
if [ -d /home/Ento/LepmonOS/packages ]; then
  pip install --break-system-packages /home/Ento/LepmonOS/packages/*.whl || true
fi

# ---------------------------------------------------------------------------
# VimbaX SDK for Allied Vision cameras
# ---------------------------------------------------------------------------
VIMBA_DIR="/opt/VimbaX"
if [ ! -d "$VIMBA_DIR" ]; then
  echo "=== Installing VimbaX SDK ==="
  cd /tmp
  
  # Download with retries and better error handling
  VIMBA_URL="https://github.com/openUC2/ImSwitchDockerInstall/releases/download/imswitch-master/VimbaX_Setup-2025-1-Linux_ARM64.tar.gz"
  VIMBA_TAR="VimbaX_Setup-2025-1-Linux_ARM64.tar.gz"
  
  echo "Downloading VimbaX from $VIMBA_URL ..."
  wget --tries=3 --timeout=30 -O "$VIMBA_TAR" "$VIMBA_URL"
  
  if [ ! -f "$VIMBA_TAR" ] || [ ! -s "$VIMBA_TAR" ]; then
    echo "ERROR: VimbaX download failed or file is empty!"
    echo "Please install VimbaX manually after boot."
  else
    echo "Extracting VimbaX..."
    tar -xzf "$VIMBA_TAR" -C /opt
    
    # Find the actual extracted directory
    EXTRACTED_DIR=$(find /opt -maxdepth 1 -type d -name "VimbaX*" 2>/dev/null | head -1)
    if [ -n "$EXTRACTED_DIR" ] && [ "$EXTRACTED_DIR" != "/opt/VimbaX" ]; then
      rm -rf "$VIMBA_DIR" 2>/dev/null || true
      mv "$EXTRACTED_DIR" "$VIMBA_DIR"
      echo "VimbaX extracted to $VIMBA_DIR"
    elif [ -d "$VIMBA_DIR" ]; then
      echo "VimbaX extracted to $VIMBA_DIR"
    else
      echo "ERROR: VimbaX extraction failed - directory not found!"
    fi
    
    rm -f "$VIMBA_TAR"
    
    # Register GenTL transport layer
    if [ -d "$VIMBA_DIR/cti" ]; then
      echo "Registering GenTL transport layer..."
      cd "$VIMBA_DIR/cti"
      bash ./Install_GenTL_Path.sh || echo "GenTL registration failed"
    fi
    
    # Find libVmbC.so in the actual structure
    VIMBA_LIB=$(find "$VIMBA_DIR" -name "libVmbC.so" 2>/dev/null | head -1)
    if [ -n "$VIMBA_LIB" ]; then
      LIB_DIR=$(dirname "$VIMBA_LIB")
      echo "✓ VimbaX installation verified (libVmbC.so): $VIMBA_LIB"
      
      # Update environment with actual library location
      cat > /etc/profile.d/vimbax.sh <<VENV2
export VIMBA_HOME="$VIMBA_DIR"
export GENICAM_GENTL64_PATH="$VIMBA_DIR/cti"
export LD_LIBRARY_PATH="\${LD_LIBRARY_PATH:+\${LD_LIBRARY_PATH}:}$LIB_DIR"
VENV2
      
      # Register with ldconfig
      echo "$LIB_DIR" > /etc/ld.so.conf.d/vimbax.conf
      ldconfig
    else
      echo "✗ WARNING: VimbaX installation incomplete - libVmbC.so not found!"
    fi
  fi
else
  echo "VimbaX already installed at $VIMBA_DIR"
fi

# Environment variables for VimbaX (available to all users)
cat > /etc/profile.d/vimbax.sh <<'VENV'
export VIMBA_HOME="/opt/VimbaX"
export GENICAM_GENTL64_PATH="/opt/VimbaX/cti"
export LD_LIBRARY_PATH="${LD_LIBRARY_PATH:+${LD_LIBRARY_PATH}:}/opt/VimbaX/api/lib"
VENV

# Register VimbaX libraries with ldconfig
if [ -d "$VIMBA_DIR/api/lib" ]; then
  echo "$VIMBA_DIR/api/lib" > /etc/ld.so.conf.d/vimbax.conf
  ldconfig
  echo "✓ VimbaX libraries registered with ldconfig"
else
  echo "✗ WARNING: $VIMBA_DIR/api/lib not found - skipping ldconfig"
fi

# Install VmbPy wheel
echo "Installing VmbPy Python bindings..."
pip install --break-system-packages \
  "https://github.com/alliedvision/VmbPy/releases/download/1.2.1_beta1/vmbpy-1.2.1-py3-none-manylinux_2_27_aarch64.whl"

# Verify VmbPy installation
if python3 -c "import vmbpy" 2>/dev/null; then
  echo "✓ VmbPy installed successfully"
else
  echo "✗ WARNING: VmbPy import failed"
fi

# ---------------------------------------------------------------------------
# Clean pip cache
# ---------------------------------------------------------------------------
pip cache purge 2>/dev/null || true
rm -rf /root/.cache/pip

# ---------------------------------------------------------------------------
# Set Python capability for privileged port binding
# ---------------------------------------------------------------------------
which python3.11 && setcap 'cap_net_bind_service=+ep' "$(which python3.11)" || true
which python3    && setcap 'cap_net_bind_service=+ep' "$(which python3)"    || true

# ---------------------------------------------------------------------------
# Log directory
# ---------------------------------------------------------------------------
mkdir -p /var/log/lepmon
chown Ento:Ento /var/log/lepmon

# ===========================================================================
# systemd services
# ===========================================================================

cat <<'UNIT' > /etc/systemd/system/lepmon-main.service
[Unit]
Description=Lepmon Main Application - Insect Timelapse Capture
After=network.target lepmon-web.service
Wants=lepmon-web.service

[Service]
Type=simple
User=Ento
WorkingDirectory=/home/Ento/LepmonOS
Environment=VIMBA_HOME=/opt/VimbaX
Environment=GENICAM_GENTL64_PATH=/opt/VimbaX/cti
Environment=LD_LIBRARY_PATH=/opt/VimbaX/api/lib
ExecStart=/usr/bin/python3 /home/Ento/LepmonOS/Main.py
Restart=on-failure
RestartSec=10
StandardOutput=append:/var/log/lepmon/main.log
StandardError=append:/var/log/lepmon/main.log

[Install]
WantedBy=multi-user.target
UNIT

cat <<'UNIT' > /etc/systemd/system/lepmon-web.service
[Unit]
Description=Lepmon Web Service - FastAPI Camera Streaming and Focus UI
After=network.target

[Service]
Type=simple
User=Ento
WorkingDirectory=/home/Ento/LepmonOS
Environment=VIMBA_HOME=/opt/VimbaX
Environment=GENICAM_GENTL64_PATH=/opt/VimbaX/cti
Environment=LD_LIBRARY_PATH=/opt/VimbaX/api/lib
ExecStart=/usr/bin/python3 /home/Ento/LepmonOS/lepmon_web_service.py --host 0.0.0.0 --port 8080
Restart=on-failure
RestartSec=5
StandardOutput=append:/var/log/lepmon/web.log
StandardError=append:/var/log/lepmon/web.log

[Install]
WantedBy=multi-user.target
UNIT

systemctl enable lepmon-main.service
systemctl enable lepmon-web.service

# ===========================================================================
# WiFi Access Point
# ===========================================================================

# NetworkManager must NOT manage wlan0
mkdir -p /etc/NetworkManager/conf.d
cat > /etc/NetworkManager/conf.d/99-unmanaged-wlan0.conf <<'EOF'
[keyfile]
unmanaged-devices=interface-name:wlan0
EOF

cat > /etc/NetworkManager/NetworkManager.conf <<'EOF'
[main]
plugins=ifupdown,keyfile

[ifupdown]
managed=false
EOF

# wpa_supplicant must NOT grab wlan0
systemctl disable wpa_supplicant.service       2>/dev/null || true
systemctl disable wpa_supplicant@wlan0.service 2>/dev/null || true
systemctl mask    wpa_supplicant.service       2>/dev/null || true
systemctl mask    wpa_supplicant@wlan0.service 2>/dev/null || true

# -- SSID generator (Python, MAC-based) --
install -d /etc/lepmon
cat <<'PY' > /usr/local/bin/lepmon-generate-ssid
#!/usr/bin/env python3
import hashlib, pathlib
ADJ  = ["Swift","Quick","Bright","Smart","Rapid","Sharp","Clear","Fast","Light","Active"]
NOUN = ["Trap","Monitor","Sensor","Detector","Scanner","Watcher","Observer","Tracker","Logger","Capture"]
mac  = pathlib.Path('/sys/class/net/wlan0/address').read_text().strip()
m    = bytes.fromhex(mac.replace(':',''))
h    = hashlib.sha256(m).digest()
print(f"Lepmon-{ADJ[((h[0]<<8)|h[1])%len(ADJ)]}-{NOUN[((h[2]<<8)|h[3])%len(NOUN)]}")
PY
chmod +x /usr/local/bin/lepmon-generate-ssid

# -- AP configurator (runs on every boot) --
# NOTE: WPA2 passphrase MUST be 8-63 characters
cat > /usr/local/bin/lepmon-configure-ap <<'AP'
#!/bin/bash
set -e
exec 1> >(logger -s -t lepmon-configure-ap) 2>&1

echo "Starting Lepmon AP configuration..."
PASSPHRASE="lepmon12"
SSID_FILE="/etc/lepmon/ssid"

for i in {1..10}; do
  [ -e /sys/class/net/wlan0/address ] && break
  echo "Waiting for wlan0... $i/10"; sleep 1
done
[ ! -e /sys/class/net/wlan0/address ] && { echo "ERROR: wlan0 not found"; exit 1; }

if [ ! -s "$SSID_FILE" ]; then
  SSID="$(/usr/local/bin/lepmon-generate-ssid)"
  echo "Generated SSID: $SSID"
  install -d /etc/lepmon
  echo "$SSID" > "$SSID_FILE"
  chmod 644 "$SSID_FILE"
else
  SSID="$(cat "$SSID_FILE")"
  echo "Using cached SSID: $SSID"
fi

install -d /etc/hostapd
cat > /etc/hostapd/hostapd.conf <<EOF
interface=wlan0
driver=nl80211
ssid=${SSID}
hw_mode=g
channel=6
wmm_enabled=1
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase=${PASSPHRASE}
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP
country_code=DK
ieee80211d=1
ieee80211n=1
EOF

echo 'DAEMON_CONF="/etc/hostapd/hostapd.conf"' > /etc/default/hostapd
echo "AP ready  SSID=$SSID  Pass=$PASSPHRASE  MAC=$(cat /sys/class/net/wlan0/address)"
AP
chmod +x /usr/local/bin/lepmon-configure-ap

# -- dnsmasq --
mkdir -p /etc/dnsmasq.d
cat > /etc/dnsmasq.d/lepmon-ap.conf <<'DNS'
interface=wlan0
bind-interfaces
dhcp-range=192.168.4.2,192.168.4.200,255.255.255.0,24h
domain=lepmon.local
local=/lepmon.local/
address=/lepmon.local/192.168.4.1
no-resolv
server=8.8.8.8
server=8.8.4.4
DNS

# -- IP forwarding + nftables NAT --
echo 'net.ipv4.ip_forward=1' > /etc/sysctl.d/99-lepmon-ipforward.conf
cat > /etc/nftables.conf <<'NFT'
flush ruleset
table inet filter {
  chain forward {
    type filter hook forward priority 0; policy drop;
    iifname "wlan0" oifname "eth0" accept
    iifname "eth0"  oifname "wlan0" ct state related,established accept
  }
}
table ip nat {
  chain postrouting {
    type nat hook postrouting priority 100;
    oifname "eth0" masquerade
  }
}
NFT
systemctl enable nftables

# -- Hotspot bootstrap service --
cat > /etc/systemd/system/lepmon-hotspot.service <<'HOTSPOT'
[Unit]
Description=Prepare wlan0 for Lepmon Access Point
After=network-online.target
Wants=network-online.target
Before=hostapd.service dnsmasq.service

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/bin/bash -c 'rfkill unblock all || true'
ExecStart=/bin/bash -c 'sleep 2'
ExecStart=/bin/bash -c 'nmcli dev set wlan0 managed no 2>/dev/null || true'
ExecStart=/bin/bash -c 'sleep 1'
ExecStart=/bin/bash -c 'ip link set wlan0 down || true'
ExecStart=/bin/bash -c 'ip addr flush dev wlan0 || true'
ExecStart=/bin/bash -c 'ip addr add 192.168.4.1/24 dev wlan0 || true'
ExecStart=/bin/bash -c 'ip link set wlan0 up || true'
ExecStart=/usr/local/bin/lepmon-configure-ap

[Install]
WantedBy=multi-user.target
HOTSPOT
systemctl enable lepmon-hotspot.service
systemctl enable hostapd
systemctl enable dnsmasq

# ===========================================================================
# Lepmon-info helper (shown on login)
# ===========================================================================
cat <<'INFO' > /usr/local/bin/lepmon-info
#!/bin/bash
echo "╔══════════════════════════════════════════╗"
echo "║       Lepmon System Information          ║"
echo "║   Insect Timelapse Monitoring System     ║"
echo "╚══════════════════════════════════════════╝"
echo ""
echo "Services:"
for svc in lepmon-main lepmon-web hostapd dnsmasq lepmon-hotspot; do
  systemctl is-active "$svc" >/dev/null 2>&1 \
    && echo "  ✓ $svc: active" \
    || echo "  ✗ $svc: inactive"
done
echo ""

ETH_IP=$(ip -4 addr show eth0 2>/dev/null | sed -n 's|.*inet \([0-9./]*\).*|\1|p')
echo "Network:"
echo "  eth0 IP : ${ETH_IP:-not configured}"
if [ -e /sys/class/net/wlan0/address ]; then
  WLAN_IP=$(ip -4 addr show wlan0 2>/dev/null | sed -n 's|.*inet \([0-9./]*\).*|\1|p')
  echo "  wlan0 IP: ${WLAN_IP:-not configured}"
fi
if [ -f /etc/lepmon/ssid ]; then
  echo ""
  echo "WiFi AP:"
  echo "  SSID    : $(cat /etc/lepmon/ssid)"
  echo "  Password: lepmon12"
  echo "  AP IP   : 192.168.4.1"
fi

echo ""
echo "Quick access:"
echo "  Web UI : http://192.168.4.1:8080/  (or http://${ETH_IP%/*}:8080/)"
echo "  SSH    : ssh Ento@192.168.4.1       Password: lepmon"
echo ""
echo "Manage services:           (see SERVICE_GUIDE.md for details)"
echo "  sudo systemctl status  lepmon-main"
echo "  sudo systemctl restart lepmon-main"
echo "  sudo journalctl -u lepmon-main -f"
echo ""
INFO
chmod +x /usr/local/bin/lepmon-info

cat >> /home/Ento/.bashrc <<'BASHRC'

# Display Lepmon info on login
if [ -x /usr/local/bin/lepmon-info ]; then
  /usr/local/bin/lepmon-info
fi
BASHRC
chown Ento:Ento /home/Ento/.bashrc

# ---------------------------------------------------------------------------
systemctl daemon-reload
echo "=== Lepmon installation complete ==="
