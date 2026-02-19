# Lepmon Service Guide

Quick reference for managing the Lepmon system on the Raspberry Pi.

---

## Default Credentials

| What              | Value                                    |
|-------------------|------------------------------------------|
| Linux user        | `Ento`                                   |
| Linux password    | `lepmon`                                 |
| WiFi AP SSID      | `Lepmon-XXXX-XXXX` (unique per device)   |
| WiFi AP password  | `lepmon12`                               |
| AP IP address     | `192.168.4.1`                            |
| Web UI            | `http://192.168.4.1:8080/`               |

---

## Services Overview

Lepmon runs as several **systemd** services:

| Service               | Description                                          |
|-----------------------|------------------------------------------------------|
| `lepmon-main`         | Main timelapse capture application (`Main.py`)       |
| `lepmon-web`          | FastAPI web service for camera streaming (`lepmon_web_service.py`) |
| `lepmon-hotspot`      | Prepares wlan0 and generates AP config on boot       |
| `hostapd`             | WiFi Access Point daemon                             |
| `dnsmasq`             | DHCP + DNS server for AP clients                     |
| `nftables`            | Firewall / NAT for internet sharing via Ethernet     |

---


## Checking devices

```
i2cdetect -y 1
```

## Checking Service Status

```bash
# Check all Lepmon services at once
sudo systemctl status lepmon-main lepmon-web lepmon-hotspot hostapd dnsmasq

# Check a single service
sudo systemctl status lepmon-main

# Quick one-liner to see which are running
for svc in lepmon-main lepmon-web hostapd dnsmasq lepmon-hotspot; do
  printf "%-20s %s\n" "$svc" "$(systemctl is-active $svc)"
done
```

---

## Starting / Stopping / Restarting Services

```bash
# --- Main Application ---
sudo systemctl start   lepmon-main      # Start capture loop
sudo systemctl stop    lepmon-main      # Stop capture loop
sudo systemctl restart lepmon-main      # Restart capture loop

# --- Web Service ---
sudo systemctl start   lepmon-web
sudo systemctl stop    lepmon-web
sudo systemctl restart lepmon-web

# --- WiFi Access Point (all 3 must be restarted together) ---
sudo systemctl restart lepmon-hotspot hostapd dnsmasq
```

---

## Viewing Logs

### Journal logs (live, follows output)

```bash
# Main application
sudo journalctl -u lepmon-main -f

# Web service
sudo journalctl -u lepmon-web -f

# Access Point / WiFi
sudo journalctl -u lepmon-hotspot -u hostapd -u dnsmasq -f

# All Lepmon services combined
sudo journalctl -u lepmon-main -u lepmon-web -u lepmon-hotspot -f
```

### Log files on disk

```bash
# Main application log
tail -f /var/log/lepmon/main.log

# Web service log
tail -f /var/log/lepmon/web.log
```

### Show last 50 lines of a service

```bash
sudo journalctl -u lepmon-main --no-pager -n 50
```

---

## Enable / Disable Services at Boot

```bash
# Disable a service (it won't start on next boot)
sudo systemctl disable lepmon-main

# Re-enable it
sudo systemctl enable lepmon-main
```

---

## Manual Execution (for Debugging)

You can run the applications directly in a terminal to see output interactively:

```bash
# Stop the service first
sudo systemctl stop lepmon-main

# Run manually
cd /home/Ento/LepmonOS
export GENICAM_GENTL64_PATH=/opt/VimbaX/cti
python3 Main.py

# Same for web service
sudo systemctl stop lepmon-web
python3 lepmon_web_service.py --host 0.0.0.0 --port 8080
```

---

## Network Access

### Via WiFi Access Point
1. Look for WiFi network `Lepmon-XXXX-XXXX`
2. Connect with password `lepmon12`
3. Open `http://192.168.4.1:8080/` in a browser
4. SSH: `ssh Ento@192.168.4.1`

### Via Ethernet
1. Connect an Ethernet cable
2. Find the IP: `ip addr show eth0`
3. Open `http://<eth0-ip>:8080/` in a browser
4. SSH: `ssh Ento@<eth0-ip>`

---

## Troubleshooting

### hostapd won't start

```bash
# Check what's wrong
sudo systemctl status hostapd
sudo journalctl -u hostapd --no-pager -n 20

# Common fix: regenerate AP config
sudo /usr/local/bin/lepmon-configure-ap
sudo systemctl restart hostapd
```

### WiFi AP not visible

```bash
# Check if wlan0 has the right IP
ip addr show wlan0

# Restart the full AP stack
sudo systemctl restart lepmon-hotspot hostapd dnsmasq
```

### Camera not detected / Vimba import errors

If you get `VimbaSystemError: No suitable Vimba installation found`:

**First, verify VimbaX is actually installed:**
```bash
ls -la /opt/VimbaX/api/lib/libVimbaC.so
```

**If file NOT found, VimbaX is missing - install it:**
```bash
sudo bash /home/Ento/LepmonOS/install_vimbax_manual.sh
```

**If file exists, check environment variables:**
```bash
# Check all VimbaX environment variables
echo $VIMBA_HOME              # Should show /opt/VimbaX
echo $GENICAM_GENTL64_PATH    # Should show /opt/VimbaX/cti
echo $LD_LIBRARY_PATH         # Should include /opt/VimbaX/api/lib

# If empty, load environment
source /etc/profile.d/vimbax.sh

# Verify library is registered
ldconfig -p | grep VimbaC

# Test import
python3 -c "from vmbpy import *; print('VmbPy OK')"
```

**Common issues:**
1. **VimbaX not installed**: The download may have failed during image build. Run manual install script.
2. **Wrong Python package**: Make sure you have `vmbpy` not `vimba` old version
3. **USB permissions**: Camera may need udev rules (usually auto-configured by VimbaX installer)

**Check USB camera:**
```bash
lsusb | grep Allied
# Should show Allied Vision camera
```

**For systemd services:** The environment is already set in the service files. Restart services after fixing:
```bash
sudo systemctl restart lepmon-main lepmon-web
```

### Python import errors

```bash
# Check if packages are installed
pip list | grep -i <package-name>

# Install missing package
sudo pip install --break-system-packages <package-name>
```

### I2C devices not detected

```bash
# Scan I2C bus
sudo i2cdetect -y 1

# If nothing shows up, check config.txt
grep i2c /boot/firmware/config.txt
# Should contain: dtparam=i2c_arm=on
```

### Serial / UART not working

```bash
# Check if UART is enabled
grep uart /boot/firmware/config.txt
# Should contain: enable_uart=1

# Test serial port
ls -la /dev/ttyS0 /dev/ttyAMA0
```

---

## USB Storage Auto-Mount

Lepmon OS automatically mounts USB mass-storage devices as soon as they are plugged in.
No desktop environment or manual configuration is required.

| Detail | Value |
|---|---|
| Mount base | `/media/usb/` |
| Mount path | `/media/usb/<PARTITION_LABEL>` (device name used when unlabelled) |
| Supported filesystems | FAT32, exFAT, NTFS, ext2/3/4, btrfs, xfs |
| Ownership | `Ento` (uid 1000) for FAT/exFAT/NTFS; native for ext* |

### Check currently mounted USB drives

```bash
ls /media/usb/
# or with full details
findmnt | grep /media/usb
```

### Safely unmount before removing the drive

```bash
# By mount point
sudo umount /media/usb/<LABEL>

# Or by stopping the systemd service instance
sudo systemctl stop usb-mount@sda1.service   # adjust device name (sda1, sdb1, …)
```

### Logs

Mount and unmount events are written to the system journal with the tag `usb-mount`:

```bash
sudo journalctl -t usb-mount -f
```

### How it works

The feature is implemented as three components installed during SD-card build:

1. **udev rule** `/etc/udev/rules.d/99-lepmon-usb-mount.rules`  
   Watches for USB block-device add/remove events and starts/stops the service.

2. **systemd service template** `usb-mount@.service`  
   One instance per partition (e.g. `usb-mount@sda1.service`).  
   `RemainAfterExit=yes` keeps the instance alive so a plain `stop` triggers the `ExecStop` unmount.

3. **Helper script** `/usr/local/bin/usb-mount.sh`  
   Detects the filesystem type via `blkid`, creates the mount point, mounts with appropriate options, and cleans up on removal.

---

## System Info

Run `lepmon-info` at any time to see a summary of services, network, USB drives, and access info.

```bash
lepmon-info
```

---

## File Locations

| Path                                              | Description                      |
|---------------------------------------------------|----------------------------------|
| `/home/Ento/LepmonOS/`                            | Application source code          |
| `/var/log/lepmon/main.log`                        | Main application log             |
| `/var/log/lepmon/web.log`                         | Web service log                  |
| `/opt/VimbaX/`                                    | VimbaX SDK for Allied Vision     |
| `/etc/lepmon/ssid`                                | Cached WiFi AP SSID              |
| `/etc/hostapd/hostapd.conf`                       | Access Point configuration       |
| `/etc/dnsmasq.d/lepmon-ap.conf`                   | DHCP configuration               |
| `/boot/firmware/config.txt`                       | Raspberry Pi hardware config     |
| `/media/usb/`                                     | USB drive mount base directory   |
| `/etc/udev/rules.d/99-lepmon-usb-mount.rules`     | udev rule for USB automount      |
| `/etc/systemd/system/usb-mount@.service`          | systemd service template         |
| `/usr/local/bin/usb-mount.sh`                     | USB mount/unmount helper script  |
