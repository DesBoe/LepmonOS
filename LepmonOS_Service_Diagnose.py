
import adafruit_bh1750      #Lichtsensor
import bme280               #Außensensor
from ina226 import INA226   #Strommesser
import adafruit_pct2075     #Innensensor
import adafruit_ds3231      #Uhr
import time
import board
import busio
import smbus2
from vmbpy import *
import cv2
import os
import random
import logging
import re
from gpiozero import LED
from LepmonOS_Dev_Camera_loop import * 
from picamera2 import Picamera2, Preview



from GPIO_Setup import *
from OLED_panel import *
from Lights import *
from datetime import datetime
import time
from service import get_usb_path
from fram_direct import *

try:
    ina = INA226(busnum=1, max_expected_amps=10, log_level=logging.INFO)
    ina.configure()
    ina.set_low_battery(5)
except Exception as e:
    print(f"Fehler beim Initialisieren des INA226: {e}")

def groesse_in_kb(pfad):
    if os.path.isfile(pfad):
        size = os.path.getsize(pfad)
    else:
        size = sum(
            os.path.getsize(os.path.join(w, f))
            for w, _, files in os.walk(pfad)
            for f in files if os.path.isfile(os.path.join(w, f))
        )
    return round(size / 1024, 0)

           
def display_text(line1=None, line2=None, line3=None, line4=None, line5=None, line6=None, sleeptime=0):
    global zeile1, zeile2, zeile3, zeile4, zeile5, zeile6
    # Nur die übergebenen Zeilen aktualisieren, andere behalten
    if line1 is not None:
        zeile1 = line1
    if line2 is not None:
        zeile2 = line2
    if line3 is not None:
        zeile3 = line3
    if line4 is not None:
        zeile4 = line4
    if line5 is not None:
        zeile5 = line5
    if line6 is not None:
        zeile6 = line6
    try:
        with canvas(oled) as draw:
            draw.text((2, 1),  zeile1, font=oled_font, fill="white")
            draw.text((2, 11), zeile2, font=oled_font, fill="white")
            draw.text((2, 21), zeile3, font=oled_font, fill="white")
            draw.text((2, 31), zeile4, font=oled_font, fill="white")
            draw.text((2, 41), zeile5, font=oled_font, fill="white")
            draw.text((2, 51), zeile6, font=oled_font, fill="white")
        time.sleep(sleeptime)
    except:
        pass
    
def set_sn():
    valid = False
    while not valid:
        sn = input("Seriennummer im Format 123456: ").strip().upper()
        sn = f"SN{sn}"  # Formatieren der Seriennummer
        if len(sn) == 8 and sn.startswith("SN") and re.match(r"^SN\d{6}$", sn):
            valid = True
            print(f"Seriennummer: {sn}") 
            write_fram(0x0110, sn)
            
            return sn   

        if not sn.startswith("SN") or not re.match(r"^SN\d{6}$", sn):
            print("Ungültiges Format. Beispiel: 123456")
        
       
def log_pfad(sn):
    usb_path,_ = get_usb_path("manual")
    log_dateipfad = f"{usb_path}/Lepmon_Diagnose_{sn}_log.log"
  
    return log_dateipfad
    
def log_schreiben(text):
  lokale_Zeit = datetime.now().strftime("%H:%M:%S")
  print(text)
  log_dateipfad = log_pfad(sn)
  try:
        # Initiales Erstellen des Logfiles
        if not os.path.exists(log_dateipfad):
            with open(log_dateipfad, 'w') as f:
                f.write(f"{lokale_Zeit}; Logfile erstellt: {log_dateipfad}\n")
                print(f"logdatei erstellt:{log_dateipfad}")
        elif os.path.exists(log_dateipfad):
            with open(log_dateipfad, 'a') as f:
                f.write(f"{lokale_Zeit}; {text}" + '\n')
               
  except Exception as e:
        lokale_Zeit = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"{lokale_Zeit}; Fehler beim loggen: {e}")
        return None
    
def LEDs():
    log_schreiben("Teste Kontroll LEDs")
    for i in range(6):
        try:
            with canvas(oled) as draw:
                draw.rectangle(oled.bounding_box, outline="white", fill="white")
        except Exception as e:
            log_schreiben(f"Fehler im Display:{e}")        
        turn_on_led("rot")
        turn_on_led("blau")
        turn_on_led("gelb")
        time.sleep(.5) 
        turn_off_led("rot")
        turn_off_led("blau")
        turn_off_led("gelb") 
        time.sleep(.5)
      
      
def update_sensor_data(lib,key, value):
    lib[key] = value      


def read_sensor_data():
    try:
        LUX = adafruit_bh1750.BH1750(i2c)
        LUX = round(LUX.lux,0)
        Sensorstatus_Licht = 1
    except Exception as e:
        LUX = "---"
        Sensorstatus_Licht = 0
        log_schreiben(f"Fehler im Lichtsensor: {e}")
     
    log_schreiben(f"Sensorstatus Licht:{Sensorstatus_Licht}")
    log_schreiben(f"Umgebungshelligkeit:{LUX}")    

    try:
        Temp_in = adafruit_pct2075.PCT2075(i2c)
        Temp_in = round(Temp_in.temperature,0)
        Sensorstatus_Inne = 1
    except Exception as e:
        Temp_in = "---"
        Sensorstatus_Inne = 0
        log_schreiben(f"Fehler im Innensensor: {e}")
    log_schreiben(f"Sensorstatus Inne:{Sensorstatus_Inne}")
    log_schreiben(f"Innentemperatur:{Temp_in}")            
        

    try:
        Sensorstatus_Strom = 1

        ina.wake(3)
        time.sleep(0.2)

        power = round(ina.power(),0)

    except Exception as e:
        power = "---"
        Sensorstatus_Strom = 0
        log_schreiben(f"Fehler im Stomsensor: {e}")

    log_schreiben(f"Stromsensor:{Sensorstatus_Strom}")
    log_schreiben(f"Leistung:{power}")


    try:
        calibration_params = bme280.load_calibration_params(bus, address)
        Außensensor = bme280.sample(bus, address, calibration_params)
        Luftdruck = round(Außensensor.pressure,0)
        Status_außen = 1
    except Exception as e:
        Luftdruck = "---"
        Status_außen = 0
        log_schreiben(f"Fehler im Außensensor: {e}")

    log_schreiben(f"Außensensor:{Status_außen}")
    log_schreiben(f"Luftdruck:{Luftdruck}")
    
    return LUX, Sensorstatus_Licht, Temp_in,Sensorstatus_Inne,power,Sensorstatus_Strom,Luftdruck,Status_außen

    
def nehme_bild_auf(sn, sensor=sensor): 
    
    usb_path,_ = get_usb_path("manual")
    dateipfad = f"{usb_path}/Lepmon_Diagnose_{sn}_Testbild.jpg"

    if sensor == "imx183": # AV
        try:
            with Vimba.get_instance() as vimba:
                cams = vimba.get_all_cameras()
                with cams[0] as cam:
                    log_schreiben("Kamera gefunden")  
                    cam.set_pixel_format(PixelFormat.Bgr8)
                    settings_file = '/home/Ento/LepmonOS/Kamera_Einstellungen.xml'.format(cam.get_id())
                    cam.load_settings(settings_file, PersistType.All)                 
                    frame = cam.get_frame(timeout_ms=5000).as_opencv_image()
                    log_schreiben("frame aufgenommen")
                    cv2.imwrite(dateipfad, frame)
                    log_schreiben(f"Bild gespeichert:{dateipfad}")
                    log_schreiben(f"Achtung!: Kontrollieren, ob {dateipfad} ein vollständiges Bild ist")

                                
        except Exception as e:
            log_schreiben(f"Fehler beim Bilderspeichern: {e}")
            
    elif sensor == "imx708":    
        try:
            Gain, Exposure, focus = 5.0, 140, 4.55  # Beispielwerte
            picam2 = Picamera2()
            picam2.options["quality"] = compression_quality
            camera_config = picam2.create_still_configuration(main={"size": (4608, 2592)})
            picam2.configure(camera_config)
            picam2.start()
                     
            picam2.set_controls({"AnalogueGain": Gain, 
                             "ExposureTime": Exposure * 1000, 
                             "AwbEnable": True,
                             #"AfMode": controls.AfModeEnum.Continuous,
                             "AfMode": controls.AfModeEnum.Manual,
                            "LensPosition": focus  # Autofokus auf gefundenen Wert setzen
                             })
            time.sleep(3) # wait for settings to take effect
        except Exception as e:
            log_schreiben(f"Fehler beim Initialisieren der Pi Kamera: {e}")



    elif sensor == "imx477":
        try:
            Gain, Exposure, focus = 5.0, 140, 4.55  # Beispielwerte
            picam2 = Picamera2()
            camera_config = picam2.create_still_configuration(main={"size": (4056, 3040)})
            picam2.configure(camera_config)
            picam2.start()
            picam2.set_controls({"AnalogueGain": Gain, 
                             "ExposureTime": Exposure * 1000, 
                             "AwbEnable": True,
                             })
            time.sleep(3) # wait for settings to take effect
        except Exception as e:
            log_schreiben(f"Fehler beim Initialisieren der Pi Kamera: {e}")
            
    if sensor == "imx708" or sensor == "imx477":
        try:
            picam2.capture_file(dateipfad)
            metadata = picam2.capture_metadata()
        except Exception as e:
            log_schreiben(f"Fehler beim Speichern des Bildes: {e}")
    
        try:
            picam2.stop()
            picam2.close() # shutdown camera
        except Exception as e:
            print(f"Fehler beim Schließen der Kamera: {e}")

    return dateipfad


def Zeit_aktualisieren():
    try:
        i2c = board.I2C()
        rtc = adafruit_ds3231.DS3231(i2c)   
        t = rtc.datetime
        dt = datetime(t.tm_year, t.tm_mon, t.tm_mday, t.tm_hour, t.tm_min, t.tm_sec)
        jetzt_local = dt.strftime("%Y-%m-%d %H:%M:%S")
        log_schreiben(f"aktuelle Uhrzeit:{jetzt_local}")
    except Exception as e:
        log_schreiben(f"RTC nicht gefunden:{e}")   
        jetzt_local = "---" 
    
    return jetzt_local  

def write_fram_random():
    zufallszahl = random.randint(100, 999)
    zufallszahl_str = str(zufallszahl)
    try:
        for offset, char in enumerate(zufallszahl_str):
            high = ((0x0577 + offset) >> 8) & 0xFF
            low = (0x0577 + offset) & 0xFF
            bus.write_i2c_block_data(FRAM_ADDRESS, high, [low, ord(char)])
        log_schreiben(f"In den Fram an Adresse 0x0577 geschrieben:{zufallszahl}")
    except Exception as e:
        log_schreiben(f"Fehler beim Schreiben von {zufallszahl} in den Fram:{e}")
        
    return zufallszahl 
 
def read_fram_bytes() -> bytes:
    result = bytearray()
    try:
        for offset in range(3):
            high = ((0x0577 + offset) >> 8) & 0xFF
            low = (0x0577 + offset) & 0xFF
            bus.write_i2c_block_data(FRAM_ADDRESS, high, [low])
            byte = bus.read_byte(FRAM_ADDRESS)
            result.append(byte)  # <-- Byte zum Ergebnis hinzufügen
        print(f"Gelesen (bytes) von 0x0577 (Länge {3}): {result.hex()}")
    except Exception as e:
        log_schreiben(f"Fehler im RAM: {e}")    
    return bytes(result) 
        
def buttons():
    up, down, right, inp, oben, unten, rechts, enter = 0,0,0,0,False,False,False,False
    if button_pressed("oben"):
        update_sensor_data(pressed, "oben", 1)
        log_schreiben("Knopf oben gedrückt")
        oben = True
        up = 1
    if button_pressed("unten"):
        update_sensor_data(pressed, "unten", 1) 
        log_schreiben("Knopf unten gedrückt")  
        unten = True
        down = 1
    if button_pressed("rechts"):
        update_sensor_data(pressed, "rechts", 1)
        log_schreiben("Knopf rechts gedrückt")  
        rechts = True
        right = 1
    if button_pressed("enter"):
        update_sensor_data(pressed, "enter", 1)  
        log_schreiben("Knopf enter gedrückt") 
        enter = True
        inp = 1
        
    return up, down, right, inp, oben, unten, rechts, enter          
               

    

if __name__ == "__main__":
    
    sn = set_sn()
        
        
    sensor = find_camera()
    log_schreiben(f"Gefundene Kamera: {sensor}")
    zeile1, zeile2, zeile3, zeile4, zeile5, zeile6 = "", "", "", "", "", ""
    oben, unten, rechts, enter = False, False, False, False
    up, down, right, inp = 0,0,0,0
    
    try:
        serial = i2c(port=1, address=0x3C)
        oled = sh1106(serial)
        oled_font = ImageFont.truetype('FreeSans.ttf', 10)
        log_schreiben("Display initialisiert")
    except:
        log_schreiben("Display nicht initialisiert")
        pass
    
    I2C_BUS = 1    
    bus = smbus2.SMBus(I2C_BUS)
    i2c = busio.I2C(board.SCL, board.SDA)
    FRAM_ADDRESS = 0x50
    port = 1
    address = 0x76
    size = 0
    gelesen = "---"
    

 
    sensor_data = {}
    pressed = {}
    camera = LED(5)
    
    
    log_schreiben("Beginne Diaganose")
    Zeit = Zeit_aktualisieren()  
    
    
    LEDs()
    print("Endloschschleife")
    
    while True:
        LUX, Sensorstatus_Licht, Temp_in,Sensorstatus_Inne,power,Sensorstatus_Strom,Luftdruck,Status_außen = read_sensor_data()
        zeile1 = f"Light:{LUX}Lux; In:{Temp_in}°C"
        zeile2 = f"Power:{power}W; out:{Luftdruck }hPa"
        zeile3 = ""
        
        geschrieben = write_fram_random()
        zeile4 = f"fram write:{geschrieben}"
        zeile5 = ""
        Zeit = Zeit_aktualisieren()
        zeile6 = Zeit
        display_text(line1=zeile1,line2=zeile2,line3=zeile3,line4=zeile4,line5=zeile5,line6=zeile6)
        
        if oben == False or unten == False or rechts == False or enter == False:
            for _ in range(50):
                up, down, right, inp, oben, unten, rechts, enter = buttons()
                pressed_str = f"▲:{up}  ▼:{down}  →:{right}  ↵:{inp} x"
                display_text(line5=pressed_str, sleeptime=0)
                time.sleep(.01)
        pressed_str = f"▲:{up}  ▼:{down}  →:{right}  ↵:{inp}"   
        Zeit = Zeit_aktualisieren()
        zeile6 = Zeit
        display_text(line5=pressed_str,line6=Zeit, sleeptime=0) 
        
        Zeile3 = "nehme Bild auf"
        display_text(line3=Zeile3, sleeptime=0) 

        if sensor == "imx183":
            camera.on()
            time.sleep(3)
        dim_up()
        LepiLED_start()
        dateipfad = None
        Bildversuche = 0
        
        
        
        
        while dateipfad is None and Bildversuche < 90:
                try:
                    dateipfad = nehme_bild_auf(sn, sensor=sensor)
                    Bildversuche = 0
                except Exception as e:
                    Bildversuche += 1
                if Bildversuche >=89:
                    log_schreiben(f"Kamera nach {Bildversuche} Versuchen nicht initalisiert") 
                camera.off()                
                
                
        Zeit = Zeit_aktualisieren()
        zeile6 = Zeit
        display_text(line6=Zeit, sleeptime=0) 
        

        LUX, Sensorstatus_Licht, Temp_in,Sensorstatus_Inne,power,Sensorstatus_Strom,Luftdruck,Status_außen = read_sensor_data()
        zeile1 = f"Light:{LUX}Lux; In:{Temp_in}°C"
        zeile2 = f"Power:{power}W; out:{Luftdruck }hPa"
        try:
            size = groesse_in_kb(dateipfad)
            log_schreiben(f"Größe des aufgenommenen Bildes:{size}kB")  
        except:
            pass  
        zeile3 = f"Bildgröße = {size}MB"
        
        gelesen = read_fram_bytes()
        gelesen_str= gelesen.decode(errors='replace')
        try:
            zahl= int(gelesen_str)
        except ValueError:
            zahl = "---"
        print(f"FRAM Zahl gelesen: {zahl}")
        zeile4 = f"fram write:{geschrieben},read:{zahl}"
        zeile5 = ""
        zeit = Zeit_aktualisieren()
        zeile6 = Zeit
        display_text(line1=zeile1,line2=zeile2,line3=zeile3,line4=zeile4,line5=zeile5,line6=zeile6)

        
        if oben == False or unten == False or rechts == False or enter == False:
            for _ in range(50):
                up, down, right, inp, oben, unten, rechts, enter = buttons()
                pressed_str = f"▲:{up}  ▼:{down}  →:{right}  ↵:{inp} x"
                display_text(line5=pressed_str, sleeptime=0)
                time.sleep(.01)
        pressed_str = f"▲:{up}  ▼:{down}  →:{right}  ↵:{inp}"  
        Zeit = Zeit_aktualisieren()
        zeile6 = Zeit
        display_text(line5=pressed_str,line6=Zeit, sleeptime=0)
        dim_down()
        LepiLED_ende()