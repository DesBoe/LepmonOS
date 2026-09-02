#!/usr/bin/env python3
from pathlib import Path
import re
import subprocess
from service import get_Lepmon_code
from logging_utils import log_schreiben
from json_read_write import *

SN_PATTERN = re.compile(r'^SN\d{6}$')

SSID_FILE = Path("/etc/lepmon/ssid")
CONFIGURE_AP = ["/usr/local/bin/lepmon-configure-ap"]
RESTART_CMD = ["sudo", "systemctl", "restart", "lepmon-hotspot", "hostapd", "dnsmasq"]


def is_valid_sn(sn: str) -> bool:
    """
    Prüft, ob eine Seriennummer dem erwarteten Format entspricht.
    Format: SN + genau 6 Ziffern (z.B. SN012345)
    """
    project_name,province, Kreis_code, sn_read = get_Lepmon_code(log_mode="manual")

    if not isinstance(sn, str) or not isinstance(sn_read, str):
        return False

    sn = sn.strip()
    return bool(SN_PATTERN.match(sn)) and sn == sn_read.strip()

def is_valid_ssid(ssid: str) -> bool:
    """
    Prüft, ob eine SSID gültig ist (1-32 Zeichen, keine führenden/folgenden Leerzeichen).
    Format: ARNI- + SN (z.B. ARNI-SN012345)
    """
    ssid = ssid.strip()
    if not (1 <= len(ssid) <= 32):
        return False
    if not ssid.startswith("ARNI-"):
        return False
    sn_part = ssid[5:]
    return is_valid_sn(sn_part)


def get_ap_ssid(log_mode="manual",
    hostapd_conf: str = "/etc/hostapd/hostapd.conf",
) -> str:
    ssid = "LEPMON-XXXX-XXXX"
    log_schreiben(f"Versuche, SSID zu ermitteln. Primär: {SSID_FILE}, Sekundär: {hostapd_conf}...", log_mode=log_mode)
    try:
        log_schreiben(f"Versuche, SSID aus {SSID_FILE} zu lesen...", log_mode=log_mode)
        p = Path(SSID_FILE)
        if p.exists():
            ssid = p.read_text(encoding="utf-8").strip()
            log_schreiben(f"Gefundene SSID in {SSID_FILE}: '{ssid}'", log_mode=log_mode)
            if ssid is not None and ssid != "":
                log_schreiben(f"SSID erfolgreich aus {SSID_FILE} gelesen: '{ssid}'", log_mode=log_mode)
                write_value_to_section("/home/Ento/LepmonOS/Lepmon_config.json", "wlan", "ssid", ssid)
                return ssid
        elif p.exists() == False or ssid == "":
                log_schreiben(f"SSID in {SSID_FILE} ist leer oder Datei existiert nicht.", log_mode=log_mode)
                raise ValueError("SSID in hostapd.conf ist leer")
    except Exception as e:
        log_schreiben(f"Fehler beim Lesen der SSID aus {SSID_FILE}: {e}", log_mode=log_mode)
    try:
        log_schreiben("Fallback: hostapd.conf parsen", log_mode=log_mode)
        h = Path(hostapd_conf)
        if h.exists():
            for line in h.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("ssid="):
                    ssid = line.split("=", 1)[1].strip()
                    log_schreiben(f"Gefundene SSID in hostapd.conf: '{ssid}'", log_mode=log_mode)
        if not h.exists() and ssid is not None and ssid != "":
            log_schreiben(f"hostapd.conf '{hostapd_conf}' existiert nicht", log_mode=log_mode)
            raise ValueError("SSID in hostapd.conf ist leer")
    except Exception as e:
        log_schreiben(f"Fehler beim Lesen der SSID aus {hostapd_conf}: {e}", log_mode=log_mode)
        log_schreiben(f"SSID konnte nicht ermittelt werden, verwende Standard: {ssid}", log_mode=log_mode)
    
    write_value_to_section("/home/Ento/LepmonOS/Lepmon_config.json", "wlan", "ssid", ssid)
    return ssid


def set_ap_ssid(log_mode="manual"):
    new_ssid = "LEPMON-XXXX-XXXX"
    try:
        project_name,province, Kreis_code, sn = get_Lepmon_code(log_mode="manual")
        log_schreiben(f"Ermittelter SN: '{sn}'", log_mode=log_mode)
        if is_valid_sn(sn):
            log_schreiben(f"SN '{sn}' entspricht dem erwarteten Format, wird als SSID verwendet.", log_mode=log_mode)
            new_ssid = f"ARNI-{sn.strip()}"
        else:        
            log_schreiben(f"SN '{sn}' entspricht nicht dem erwarteten Format, beende.", log_mode=log_mode)

        if not new_ssid:
            raise ValueError("SSID darf nicht leer sein.")
        if len(new_ssid) > 32:
            raise ValueError("SSID darf maximal 32 Zeichen haben.")
    except Exception as e:
        log_schreiben(f"Fehler beim Ermitteln der neuen SSID: {e}", log_mode=log_mode)
        log_schreiben("SSID wird nicht aktualisiert.", log_mode=log_mode)
        write_value_to_section("/home/Ento/LepmonOS/Lepmon_config.json", "wlan", "ssid", new_ssid)
        return new_ssid
    
    try:
        log_schreiben(f"Setze neue SSID: '{new_ssid}'", log_mode=log_mode)
        # SSID-Cache schreiben
        SSID_FILE.parent.mkdir(parents=True, exist_ok=True)
        SSID_FILE.write_text(new_ssid + "\n", encoding="utf-8")
        SSID_FILE.chmod(0o644)

        # hostapd.conf neu generieren und Dienste neu starten
        subprocess.run(CONFIGURE_AP, check=True)
        subprocess.run(RESTART_CMD, check=True)
    except Exception as e:
        log_schreiben(f"Fehler beim Setzen der neuen SSID: {e}", log_mode=log_mode)
    write_value_to_section("/home/Ento/LepmonOS/Lepmon_config.json", "wlan", "ssid", new_ssid)
    return new_ssid


def get_ap_password(log_mode="manual",
    hostapd_conf: str = "/etc/hostapd/hostapd.conf",
) -> str:
    """Liest das WiFi AP Passwort aus hostapd.conf."""
    h = Path(hostapd_conf)
    log_schreiben(f"Versuche, AP Passwort aus {hostapd_conf} zu lesen...", log_mode=log_mode)
    if h.exists():
        for line in h.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("wpa_passphrase="):
                password = line.split("=", 1)[1].strip()
                if password:
                    log_schreiben(f"AP Passwort gefunden in {hostapd_conf}: '{password}'", log_mode=log_mode)
                    write_value_to_section("/home/Ento/LepmonOS/Lepmon_config.json", "wlan", "password", password)
                    return password
    
    # Fallback: Standardpasswort
    log_schreiben(f"Verwende Standardpasswort: 'lepmon12'", log_mode=log_mode)
    write_value_to_section("/home/Ento/LepmonOS/Lepmon_config.json", "wlan", "password", "lepmon12")
    return "lepmon12"


if __name__ == "__main__":
    print("Modul zum Umbennen des Standard WLAN Namens und zum Auslesen des WLAN Passworts. Wird von der Startsequenz aufgerufen.")
    print("ACHTUNG!: Das Skriptläuft nur Fehlerfrei auf der SD Karte OHNE 'Fishermans Friend'")
    print("SD Karten zum Einrichten/mit 'Fishermans Friend' müssen mit diesem Skript können den Restart Command nicht ausführen.")
    print("der Fehler 'returned non zero exit status 5' ist okay und kann ignoriert werden.")


    ssid = get_ap_ssid(log_mode="manual")
    if is_valid_ssid(ssid):
        print(f"SSID ist bereits korrekt formatiert: '{ssid}'")
        ssid = "LEPMON-XXX-XXX"
        print(f"Nutze für die Demonstration eine fehlerhafte SSID, um die Funktionalität zu erzwingen: '{ssid}'.")
        
    is_valid_ssid(ssid)
    if not is_valid_ssid(ssid):

        log_mode = "manual"
        log_schreiben("----------------------------------------------", log_mode=log_mode)
        log_schreiben("Bennene WLAN um", log_mode=log_mode)

        ssid = get_ap_ssid(log_mode="manual")
        new_ssid = set_ap_ssid(log_mode="manual")
        password = get_ap_password(log_mode="manual")

        log_schreiben("==============================================", log_mode=log_mode)
        log_schreiben(f"WLAN Übersicht:", log_mode=log_mode)
        log_schreiben("----------------------------------------------", log_mode=log_mode)
        log_schreiben(f"{'Alte SSID':<22} | {ssid}", log_mode=log_mode)
        log_schreiben(f"{'Neue SSID':<22} | {new_ssid}", log_mode=log_mode)
        log_schreiben(f"{'Passwort':<22} | {password}", log_mode=log_mode)

        log_schreiben("==============================================", log_mode=log_mode)

'''
#####################
Testweise Dateien mit Terminal anlegen:
#####################

sudo mkdir -p /etc/lepmon

echo "ARNI-ab123456" | sudo tee /etc/lepmon/ssid >/dev/null
sudo chmod 644 /etc/lepmon/ssid


ls -ld /etc/lepmon
cat /etc/lepmon/ssid




#####################
lepmon-configure-ap:
#####################

sudo mkdir -p /usr/local/bin

sudo tee /usr/local/bin/lepmon-configure-ap >/dev/null <<'EOF'
#!/bin/bash
set -e
exec 1> >(logger -s -t lepmon-configure-ap) 2>&1

echo "Starting Lepmon AP configuration..."
PASSPHRASE="lepmon12"
SSID_FILE="/etc/lepmon/ssid"

for i in {1..10}; do
  [ -e /sys/class/net/wlan0/address ] && break
  echo "Waiting for wlan0... $i/10"
  sleep 1
done

[ ! -e /sys/class/net/wlan0/address ] && { echo "ERROR: wlan0 not found"; exit 1; }

if [ ! -s "$SSID_FILE" ]; then
  echo "ERROR: SSID file missing: $SSID_FILE"
  exit 1
fi

SSID="$(cat "$SSID_FILE")"

install -d /etc/hostapd
cat > /etc/hostapd/hostapd.conf <<APCONF
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
APCONF

echo 'DAEMON_CONF="/etc/hostapd/hostapd.conf"' > /etc/default/hostapd
echo "AP ready  SSID=$SSID  Pass=$PASSPHRASE  MAC=$(cat /sys/class/net/wlan0/address)"
EOF

sudo chmod +x /usr/local/bin/lepmon-configure-ap

'''