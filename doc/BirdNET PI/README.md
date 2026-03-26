# BirdNET PI Integration

Author: Franz Häring, <f.x.haering@gmail.com>

BirdNET PI is a software for Raspberry Pi 4 and higher which continually listens to birds. It identifies species using AI. The identifications are saved into a database and displayed on a website. Optionally (and this is really cool) they are sent to BirdWeather, which integrates it in space and time to a worldwide bird species map.

For now BirdNET PI cannot be run directly on the LEPMON Raspberry Pi, but it can send the microphone input stream to an audio streaming server. The necessary steps are described here.

```mermaid
---
title: Distributed BirdNET PI
---
flowchart TD

Icecast[Icecast Server]
BirdNET[BirdNET PI]

subgraph LepmonRaspi[LEPMON Raspberry Pi]
  Microphone(USB PnP Microphone)
  Raspi[["`**Raspberry Pi** 48 kHz sampling`"]]
  Microphone == "USB" ==> Raspi
end

Raspi == "mp3" ==> Icecast
Icecast == "Audio" ==> BirdNET
```

## Precondition: Internet connection

To send the audio stream to a server an internet connection is necessary. If there is LAN at the LEPMON place, just connect it and skip the rest of this chapter.

The internal Wifi adapter is not an option because it is set up as an access point. An external antenna is not possible with Raspberry Pi 4. An external USB Wifi adapter would be possible but after multiple failures I decided to use an external Wifi - LAN bridge. My choice was "TP-Link WLAN-Router TL-WR802N Nano" for about 20 Euros.

## Linux configuration

All configuration steps are initially done as the pre-existing user "Ento".

### User account

I wanted to have my own user account "fh" with SUDO rights on the Raspi:

```bash
sudo adduser fh
sudo usermod -aG sudo fh
```

### Midnight Commander and ffmpeg

I'm addicted to two-column-file-managers so I installed Midnight Commander. ffmpeg is needed too:

```bash
sudo apt update
sudo apt install mc ffmpeg -y
```

### Microphone setup

I connected a simple USB Microphone. With

```bash
arecord -L
```

the audio input sources are being listed. My micro identified as

```text
hw:CARD=Device,DEV=0
    USB PnP Sound Device, USB Audio
    Direct hardware device without any conversions
```

To be able to use it as source for multiple consumers, I made this entry to `/etc/asound.conf`:

```text
# ------------------------------------------------------------
#  USB PnP Microphone
#  - dsnoop direkt an hw (Pflicht!)
#  - danach plug für Format-/Rate-Erzwingung
#  - 48000 Hz, 1 Kanal, S16_LE
# ------------------------------------------------------------

# --- Rohes Hardware-Device ----------------------------------
pcm.usbpnp_hw {
    type hw
    card Device
    device 0
}

# --- dsnoop: Mehrere Leser gleichzeitig ---------------------
#     MUSS direkt an hw hängen!
pcm.usbpnp_dsnoop {
    type dsnoop
    ipc_key 48001
    ipc_perm 0666
    slave {
        pcm "usbpnp_hw"
        channels 1
        rate 48000
        format S16_LE
    }
}

# --- Strict plug: Erzwingt Format/Rate/Kanäle ----------------
#     Darf NACH dsnoop kommen, nicht davor.
pcm.usbpnp {
    type plug
    slave {
        pcm "usbpnp_dsnoop"
        channels 1
        rate 48000
        format S16_LE
    }
    hint {
        show on
        description "USB PnP Microphone shared capture (48kHz, 1ch)"
    }
}
```

### Audio streaming as systemd service

To send the audio stream continuously to an Icecast server I created a file `/usr/local/bin/usbpnp-direct.sh` with this content:

```text
#!/bin/bash

exec /usr/bin/ffmpeg -f alsa -ar 48000 -ac 1 -i usbpnp \
  -ar 48000 -ac 1 -c:a libmp3lame -b:a 128k -content_type audio/mpeg \
  -f mp3 icecast://source:t8Bf1u2X-b_gHg@icecast.itools.de:8000/lepmon-sn010XXX-direct.mp3
```

Replace sn010XXX by the serial number of your LEPMON Device, e.g. sn010012. Don't forget to give execution permission to it (`chmod +x /usr/local/bin/usbpnp-direct.sh`).

To test it you can execute it directly. You can hear it on https://icecast.itools.de/lepmon-sn010XXX-direct.mp3.

To make it execute automatically after power off / on, I made a systemd service:

```bash
sudo nano /etc/systemd/system/usbpnp-direct.service
```

```text
[Unit]
Description=USB PnP Microphone FFmpeg Icecast Stream
After=sound.target local-fs.target network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
Group=root

# WICHTIG: Environment für ALSA
Environment=ALSA_CARD=Device

# Neustart bei Fehlern
Restart=always
RestartSec=5

[Service]
ExecStart=/usr/local/bin/usbpnp-direct.sh
Restart=always

# Logging
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

Enable and start service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable usbpnp-direct
sudo systemctl start usbpnp-direct
sudo systemctl status usbpnp-direct
journalctl -u usbpnp-direct.service
```

The service should be enabled and active. You can check again on https://icecast.itools.de/lepmon-sn010XXX-direct.mp3.
