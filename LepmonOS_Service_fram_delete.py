from fram_direct import *
import time
from logging_utils import log_schreiben

def clear_fram(mode, log_mode = "log"):
    print("RAM Bereinigung\nStartbyte und Endbyte angeben\nBeachte Memory Map")
    if mode == "manual":
        print("❗ Manuelle Eingabe der Start- und Endbytes")
        start = int(input("❗ Startbyte (0x0100 - 0x0BFF): 0x"),16)
        end = int(input("❗ Endbyte (0x0100 - 0x0BFF): 0x"),16)
        log_schreiben(f"Manuelle RAM Bereinigung: Startbyte 0x{start:02X}, Endbyte 0x{end:02X}", log_mode)
    elif mode == "setup":
        start = 0x0118
        end = 0x0BFF   
        print("❗ Setup Modus, lösche FRAM Breich 0x0118 - 0x0BFF") 
        log_schreiben(f"Setup RAM Bereinigung: Startbyte 0x{start:02X}, Endbyte 0x{end:02X}", log_mode)
    if start < 0x0100 or start > 0x0BFF or end < 0x0100 or end > 0x0BFF:
        log_schreiben("❌ Ram Bereich kann nicht gelöscht werden, Produktionsdaten hinterlegt.", log_mode)
        return
    if start > end: 
        log_schreiben("❌ Ungültige Eingabe. Startbyte muss kleiner als Endbyte sein.", log_mode)
        return
    print("Lösche FRAM...")
    for addr in range(start, end):
        high = (addr >> 8) & 0xFF
        low = addr & 0xFF
        try:
            bus.write_i2c_block_data(FRAM_ADDRESS, high, [low, 0x00])
        except OSError:
            continue
    log_schreiben(f"✅ FRAM Bereich erfolgreich im Bereich 0x{start:02X} - 0x{end:02X} gelöscht.", log_mode)

if __name__ == "__main__":
    clear_fram("manual")