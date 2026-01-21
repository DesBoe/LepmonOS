from logging_utils import log_schreiben
import time

def add_to_bootconfig(new_entry, log_mode="log"):
    file_path = "/boot/firmware/config.txt"
    entry_clean = new_entry.strip()

    with open(file_path, "r") as f:
        lines = f.readlines()
        # prüfen, ob die Zeile schon existiert
        if entry_clean not in [line.strip() for line in lines]:
            with open(file_path, "a") as f:  # "a" = append
                f.write(entry_clean + "\n")                    
                print(f"Config.txt: Zeile hinzugefügt: {entry_clean}")
                log_schreiben(f"Zeile zu config.txt hinzugefügt: {entry_clean}", log_mode=log_mode)
                time.sleep(1)
        else:
            print("Config.txt: Zeile existiert bereits, keine Änderung vorgenommen.")
            
            
if __name__ == "__main__":
    print("Dieses Skript ist ein Modul und sollte nicht direkt ausgeführt werden.")
    add_to_bootconfig("gpio=13=op,dl","manual")