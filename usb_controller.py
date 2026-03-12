import os
import time
from logging_utils import log_schreiben
import subprocess
from json_read_write import get_value_from_section

def wait_for_write_completion():
    """
    Wartet, bis alle Schreibprozesse auf den USB-Stick abgeschlossen sind.
    """
    print("Überprüfe, ob Schreibprozesse aktiv sind...")
    while True:
        try:
            # Synchronisiere ausstehende Schreibvorgänge
            subprocess.run(["sync"], check=True)
            print("Schreibvorgänge synchronisiert.")
            break  # Wenn kein Fehler auftritt, sind alle Schreibvorgänge abgeschlossen
        except Exception as e:
            print(f"Fehler beim Synchronisieren der Schreibvorgänge: {e}")
            time.sleep(1)  # Warte 1 Sekunde und versuche es erneut

def toggle_usb_port(port_number):
    """
    Schaltet einen USB-Port aus und wieder ein.
    
    :param port_number: Die Nummer des USB-Ports (z. B. "1", "2", etc.).
    """
    usb_path = f"/sys/bus/usb/devices/usb{port_number}/authorized"
    
    if not os.path.exists(usb_path):
        print(f"USB-Port {port_number} nicht gefunden. Überprüfe die Port-Nummer.")
        return False

    try:
        # USB-Port deaktivieren
        print(f"Deaktiviere USB-Port {port_number}...")
        with open(usb_path, "w") as f:
            f.write("0")
        time.sleep(5)  # Warte 5 Sekunden

        # USB-Port aktivieren
        print(f"Aktiviere USB-Port {port_number}...")
        with open(usb_path, "w") as f:
            f.write("1")
        time.sleep(1)  # Warte 1 Sekunde

        print(f"USB-Port {port_number} wurde erfolgreich zurückgesetzt.")
        time.sleep(10)  # Wartezeit nach dem Zurücksetzen der USB-Ports
        return True
    except PermissionError:
        print("Fehler: Keine Berechtigung, um den USB-Port zu steuern. Führe das Skript mit 'sudo' aus.")
        return False
    except Exception as e:
        print(f"Fehler beim Zurücksetzen des USB-Ports {port_number}: {e}")
        return False

def reset_all_usb_ports(log_mode):
    """
    Schaltet alle USB-Ports des Raspberry Pi nacheinander aus und wieder ein.
    """
    print("Starte das Zurücksetzen aller USB-Ports...")

    # Warte, bis alle Schreibprozesse abgeschlossen sind
    wait_for_write_completion()

    for port_number in range(1, 3):  # USB-Ports 1 bis 2
        print(f"Bearbeite USB-Port {port_number}...")
        toggle_usb_port(port_number)
    print("Alle USB-Ports wurden zurückgesetzt.")



def usb_auswerfen(mount_path):
    try:
        subprocess.run(["umount", mount_path], check=True)
        print(f"{mount_path} wurde erfolgreich ausgeworfen.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Fehler beim Auswerfen: {e}")
        return False


def remount_usb_drive(log_mode):
    wait_for_write_completion()
    time.sleep(2)
    log_schreiben("Schalte USB Ports des Raspberry aus", log_mode=log_mode)
    mount_path = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "general", "usb_drive")
    success = False
    error_count = 0
    while not success:
        try:
            success = usb_auswerfen(mount_path)
        except Exception as e:
            print(f"Fehler beim Auswerfen des USB-Laufwerks: {e}")
            error_count += 1
        
        if error_count >= 10:
            print("Fehler: Das USB-Laufwerk konnte nach 10 Versuchen nicht ausgeworfen werden.")
            time.sleep(2)
            break

    time.sleep(2)
    reset_all_usb_ports(log_mode)
    time.sleep(5)
    log_schreiben("USB Ports des Raspberry eingeschaltet", log_mode=log_mode)
    log_schreiben("USB Laufwerk neu eingehängt", log_mode=log_mode)



if __name__ == "__main__":
    # Führe das Zurücksetzen aller USB-Ports aus
    remount_usb_drive(log_mode = "manual")