from fram_direct import *
import time

def clear_fram(mode):
    print("RAM Bereinigung\nStartbyte und Endbyte angeben\nBeachte Memory Map")
    if mode == "manual":
        print("❗ Manuelle Eingabe der Start- und Endbytes")
        start = int(input("❗ Startbyte (0x0100 - 0x0BFF): 0x"),16)
        end = int(input("❗ Endbyte (0x0100 - 0x0BFF): 0x"),16)
    elif mode == "setup":
        start = 0x0118
        end = 0x0BFF   
        print("❗ Setup Modus, lösche FRAM Breich 0x0118 - 0x0BFF") 
    if start < 0x0100 or start > 0x0BFF or end < 0x0100 or end > 0x0BFF:
        print("❌ Ram Bereich kann nicht gelöscht werden, Produktionsdaten hinterlegt.")
        return
    if start > end: 
        print("❌ Ungültige Eingabe. Startbyte muss kleiner als Endbyte sein.")
        return
    print("Lösche FRAM...")
    for addr in range(start, end):
        high = (addr >> 8) & 0xFF
        low = addr & 0xFF
        try:
            bus.write_i2c_block_data(FRAM_ADDRESS, high, [low, 0x00])
        except OSError:
            continue
    print("✅ FRAM Bereich erfolgreich gelöscht.")

if __name__ == "__main__":
    clear_fram("manual")