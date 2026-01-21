import subprocess
import sys
from pathlib import Path
import importlib.util
from fram_direct import *
from OLED_panel import *
from language import *
from logging_utils import *
import re
from end import trap_shutdown


def extract_package_info(whl_name):
    # Regex für Paketnamen und Version
    pattern = r"^(?P<name>[\w\-]+)-(?P<version>[\d\.]+)"
    match = re.match(pattern, whl_name)
    if match:
        return match.group("name"), match.group("version")
    return None, None

def is_installed(module_name: str) -> bool:
    """Prüft, ob ein Python-Modul importierbar ist."""
    return importlib.util.find_spec(module_name) is not None

def execute_package_installation(lang, log_mode):
    
    PACKAGE_DIR = Path("/home/Ento/LepmonOS/packages") # Ordner mit den .whl-Dateien
    
    REQUIRED_PACKAGES = { # Benötigte Pakete (Importname : pip-Name)
        "pycountry": "pycountry",
        "h3": "h3",
        "cv2": "opencv-python",
        "numpy": "numpy",
        "adafruit_bme280": "adafruit-circuitpython-bme280"
    }
    log_schreiben(f"erwarte installation für {', '.join(REQUIRED_PACKAGES.values())}", log_mode=log_mode)
    

    missing = []

    # Deinstalliere alle Pakete, die bereits installiert sind
    for module, pip_name in REQUIRED_PACKAGES.items():
        if is_installed(module):
            log_schreiben(f"{pip_name} ist bereits installiert und wird deinstalliert", log_mode=log_mode)
            try:
                subprocess.check_call([
                    sys.executable, "-m", "pip", "uninstall", "-y", pip_name, "--break-system-packages"
                ])
                log_schreiben(f"{pip_name} wurde deinstalliert", log_mode=log_mode)
            except subprocess.CalledProcessError as e:
                log_schreiben(f"Fehler beim Deinstallieren von {pip_name}: {e}", log_mode=log_mode)
            missing.append(pip_name)
        else:
            log_schreiben(f"{pip_name} fehlt bisher auf dem Raspberry Pi", log_mode=log_mode)
            missing.append(pip_name)

    if not missing:
        log_schreiben("Alle benötigten Pakete sind bereits installiert", log_mode=log_mode)
        show_message("package_2", lang=lang)
        return

    log_schreiben(f"Installiere fehlende Pakete: {', '.join(missing)}", log_mode=log_mode)

    # Installiere passende .whl-Dateien direkt, falls vorhanden
    for whl_file in PACKAGE_DIR.glob("*.whl"):
        # Ignoriere macOS-Metadaten-Dateien
        if whl_file.name.startswith("._"):
            continue
        package, version = extract_package_info(whl_file.name)
        print(package)

        show_message("package_3", lang=lang, package = str(package), version = str(version))
        log_schreiben(f"Versuche Installation von {whl_file.name} ...", log_mode=log_mode)
        try:
            subprocess.check_call([
                sys.executable, "-m", "pip", "install",
                "--no-index",
                str(whl_file),
                "--break-system-packages"
            ])
            show_message("package_4", lang=lang, package = str(package), version = str(version))
            log_schreiben(f"{whl_file.name} installiert", log_mode=log_mode)
            
        except subprocess.CalledProcessError as e:
            error_message(15, e, log_mode)

    # Prüfe, ob noch Pakete fehlen und versuche Standardinstallation
    still_missing = [pip_name for module, pip_name in REQUIRED_PACKAGES.items() if not is_installed(module)]
    if still_missing:
        show_message("package_5", lang=lang)
        log_schreiben(f"Folgende Pakete fehlen weiterhin: {', '.join(still_missing)}", log_mode=log_mode)
        cmd = [
            sys.executable, "-m", "pip", "install",
            "--no-index",
            f"--find-links={PACKAGE_DIR}",
            *still_missing,
            "--break-system-packages"
        ]
        try:
            subprocess.check_call(cmd)
            log_schreiben("Installation abgeschlossen", log_mode=log_mode)
            show_message("package_6", lang=lang)
        except subprocess.CalledProcessError as e:
            error_message(15, e, log_mode)

    else:
        log_schreiben("Alle Pakete erfolgreich installiert!", log_mode=log_mode)
        show_message("package_7", lang=lang)
        
        
        
        
        
def install_packages(log_mode):
    if read_fram_bytes(0x056F, 1) == b'\x00':
    #if True:
        lang = get_language()
        show_message("package_1", lang=lang)
        
        log_schreiben("------------------", log_mode=log_mode)
        log_schreiben("Starte Installation von Python Paketen...", log_mode=log_mode)
        try:
            execute_package_installation(lang,log_mode)
            write_fram_bytes(0x056F , b'\x01')
            log_schreiben("Installation von Python Paketen beendet", log_mode=log_mode)
            log_schreiben("##################################", log_mode=log_mode)
            log_schreiben("### SELBSTINDUZIERTER SHUTDOWN ###", log_mode=log_mode)
            log_schreiben("##################################", log_mode=log_mode) 
            trap_shutdown(log_mode,5)
            os.system("sudo reboot now")
            return
        except Exception as e:
            log_schreiben(f"Fehler bei der Paketinstallation: {e}", log_mode=log_mode)
            log_schreiben("------------------", log_mode=log_mode)
            return
            
        
        
if __name__ == "__main__":
    write_fram_bytes(0x056F, b'\x00')
    print("Kontrollbit für Paketinstallation auf x00 gesetzt.")
    time.sleep(1)
    install_packages(log_mode="manual")