import serial
from json_read_write import get_value_from_section
from datetime import datetime
import time

try:
    uart = serial.Serial("/dev/serial0", 9600, timeout=1)
except Exception as e:
    print(f"Warnung: Lora Sender nicht initialisiert: {e}")
    pass

def send_lora(main_message):
    try:
        sensor_id = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","general","serielnumber")
        message = f"{sensor_id} start of message\n{main_message}\n{sensor_id} end of message\n "
    except Exception as e:
        print("Fehler im senden der Nachricht")
    try:
        uart.write(message.encode('utf-8') + b'\n') 
        print(f"\n{message}\n")
    except Exception as e:
        print("Statusmeldung nicht mit LoraWan gesendet")    


if __name__ == "__main__":
    while True:
        sensor_id = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","general","serielnumber")
        jetzt_local = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        send_lora(f"{jetzt_local}\nHier ist ARNI\nSensor ID: {sensor_id}")     
        
        time.sleep(5)   