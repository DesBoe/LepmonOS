import adafruit_bh1750      #Lichtsensor
import bme280               #Außensensor
try:
    import adafruit_bme280.basic as adafruit_bme280  #Außensensor, nachdem es ab Januar 2026 nicht mehr wie vorher geklappt hat
except Exception as e:
    print(f"\n WARNUNG: beim Importieren von adafruit_bme280.basic: {e}"
           "\n beachte: Bei neu installiertem LEPMON OS 2.1.5+ muss das Paket 'adafruit-circuitpython-bme280' über den Paket-Installer installiert werden.")
    pass
from ina226 import INA226   #Strommesser
import adafruit_pct2075     #Innensensor
import adafruit_bmp280      #Innensensor gen 1
import time
import board
import busio
import smbus2
import json
import os
import logging
from json_read_write import get_value_from_section
from logging_utils import error_message
from hardware import get_hardware_version

from times import *


os.system('sudo raspi-config nonint do_i2c 0')
i2c = busio.I2C(board.SCL, board.SDA)

port = 1
address = 0x76
bus = smbus2.SMBus(port)

sensor_data = {}
sensor_status = {}


def update_sensor_data(lib,key, value):
    lib[key] = value
    
# ina
try:
    ina = INA226(busnum=1, address=0x40, max_expected_amps=10, log_level=logging.INFO)
    ina.configure()
    ina.set_low_battery(5)   
except Exception as e:
    print(f"Fehler in der Initialisierung des Stromsensors:{e}")  

def get_power():
    bus_voltage, shunt_voltage, current, power, Sensorstatus_Strom = "---", "---", "---", "---", 0
    hardware = get_hardware_version()
    try:         
        if hardware != "Pro_Gen_1" and hardware != "Pro_Gen_2":
            time.sleep(0.2)
            Sensorstatus_Strom = 1

            bus_voltage = round(ina.voltage(), 2)
            shunt_voltage = round(ina.shunt_voltage(), 2)
            current = round(ina.current(), 2) 
            power = round(ina.power()/1000, 2)

    except Exception as e:
        print("Fehler 7 - Stromsensor ausgefallen")

    return bus_voltage, shunt_voltage, current, power, Sensorstatus_Strom

def get_light(log_mode):
    try:
        Dämmerungsschwellenwert = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "capture_mode", "dusk_treshold")
    except Exception as e:
        error_message(11,e,log_mode)
        Dämmerungsschwellenwert = 90

    try:
        LUX = adafruit_bh1750.BH1750(i2c) 
        LUX = round(LUX.lux, 2)
        Sensorstatus_Licht = 1
    except Exception as e:
        error_message(4,e,log_mode)

        Sensorstatus_Licht = 0
        LUX = Dämmerungsschwellenwert
        
    return LUX, Sensorstatus_Licht
    
    
    
def read_sensor_data(code,lokale_Zeit, log_mode):
    hardware = get_hardware_version()

    update_sensor_data(sensor_data, "code", code)
    update_sensor_data(sensor_data, "time_read", lokale_Zeit)
    update_sensor_data(sensor_status, "time_read", lokale_Zeit)

    LUX, Sensorstatus_Licht = get_light(log_mode)
    if Sensorstatus_Licht == 0:
        update_sensor_data(sensor_data, "LUX_(Lux)", "---")
    elif Sensorstatus_Licht == 1:
        update_sensor_data(sensor_data, "LUX_(Lux)", f"{LUX:.2f}")
    update_sensor_data(sensor_status, "Light_Sensor", Sensorstatus_Licht)



    try:
        if get_hardware_version() == "Pro_Gen_1":
            Temp_in = adafruit_bmp280.Adafruit_BMP280_I2C(i2c)
        elif hardware in ["Pro_Gen_2","Pro_Gen_3",
                          "CSL_Gen_1","CSS_Gen_1"]:  
            Temp_in = adafruit_pct2075.PCT2075(i2c)             

        Temp_in = round(Temp_in.temperature, 2) 
        Sensorstatus_Inne = 1
        update_sensor_data(sensor_data, "Temp_in_(°C)", f"{Temp_in:.2f}")
    except Exception as e:
        error_message(6,e,log_mode)
        Temp_in = "---"
        update_sensor_data(sensor_data, "Temp_in_(°C)", Temp_in)
        Sensorstatus_Inne = 0
        
    update_sensor_data(sensor_data, "Inner_Sensor", Sensorstatus_Inne)
    update_sensor_data(sensor_status, "Inner_Sensor", Sensorstatus_Inne)        
    
        
    bus_voltage, shunt_voltage, current, power, Sensorstatus_Strom = get_power()
    if Sensorstatus_Strom == 0:
        update_sensor_data(sensor_data, "bus_voltage_(V)", "---")
        update_sensor_data(sensor_data, "shunt_voltage_(V)", "---")
        update_sensor_data(sensor_data, "current_(mA)", "---")
        update_sensor_data(sensor_data, "power_(W)", "---")
    elif Sensorstatus_Strom == 1:
        
        update_sensor_data(sensor_data, "bus_voltage_(V)", f"{bus_voltage:.2f}")
        update_sensor_data(sensor_data, "shunt_voltage_(V)", f"{shunt_voltage:.2f}")
        update_sensor_data(sensor_data, "current_(mA)", f"{current:.2f}")
        update_sensor_data(sensor_data, "power_(W)", f"{power:.2f}")
    update_sensor_data(sensor_data, "Power_Sensor", Sensorstatus_Strom)
    update_sensor_data(sensor_status, "Power_Sensor", Sensorstatus_Strom)


    try:
        bme280 = adafruit_bme280.Adafruit_BME280_I2C(i2c, address=0x76)
        Temperatur = round(bme280.temperature, 2)
        Luftdruck = round(bme280.pressure, 2)
        Luftfeuchte = round(bme280.humidity, 2)
        Status_außen = 1
        update_sensor_data(sensor_data, "Temp_out_(°C)", f"{Temperatur:.2f}")
        update_sensor_data(sensor_data, "air_pressure_(hPa)", f"{Luftdruck:.2f}")
        update_sensor_data(sensor_data, "air_humidity_(%)", f"{Luftfeuchte:.2f}")
        update_sensor_data(sensor_data, "Environment_Sensor", Status_außen)
    except Exception as e:
        print(f"Warnung: Außensensor konnte nicht initialisiert werden, versuche Alternative: {e}")
        
        try:
            calibration_params = bme280.load_calibration_params(bus, address)
            Außensensor = bme280.sample(bus, address, calibration_params) 
            Temperatur = round(Außensensor.temperature, 2)
            Luftdruck = round(Außensensor.pressure, 2)
            Luftfeuchte = round(Außensensor.humidity, 2)
            Status_außen = 1
            update_sensor_data(sensor_data, "Temp_out_(°C)", f"{Temperatur:.2f}")
            update_sensor_data(sensor_data, "air_pressure_(hPa)", f"{Luftdruck:.2f}")
            update_sensor_data(sensor_data, "air_humidity_(%)", f"{Luftfeuchte:.2f}")
            update_sensor_data(sensor_data, "Environment_Sensor", Status_außen)
    
        except Exception as e:
            error_message(5,e,log_mode)
            Temperatur = "---"
            Luftdruck = "---"
            Luftfeuchte = "---"
            Status_außen = 0
        
            update_sensor_data(sensor_data, "Temp_out_(°C)", Temperatur)
            update_sensor_data(sensor_data, "air_pressure_(hPa)", Luftdruck)
            update_sensor_data(sensor_data, "air_humidity_(%)", Luftfeuchte)
            update_sensor_data(sensor_data, "Environment_Sensor", Status_außen)
            pass
    update_sensor_data(sensor_status, "Environment_Sensor", Status_außen)

    return sensor_data, sensor_status










def write_sensor_data_to_json(sensor_data,sensor_status):
    file_path_data = "sensor_values.json"
    file_path_status = "sensor_status.json"

    try:
        with open(file_path_data, "w") as json_file:
            json.dump(sensor_data, json_file, indent=4)
        print(f"Sensor-Daten erfolgreich in {file_path_data} gespeichert.")
    except Exception as e:
        print(f"Fehler beim Schreiben der Sensor-Daten in die JSON-Datei: {e}")

    try:
        with open(file_path_status, "w") as json_file:
            json.dump(sensor_status, json_file, indent=4)
        print(f"Sensor-Daten erfolgreich in {file_path_status} gespeichert.")
    except Exception as e:
        print(f"Fehler beim Schreiben der status-Daten in die JSON-Datei: {e}")        


def display_sensor_data(sensor_data, sensor_status):
    """
    Liest die Dictionaries sensor_data und sensor_status und gibt die Inhalte im Terminal aus.
    Überprüft außerdem, ob in sensor_status Werte 0 enthalten sind, und gibt die betroffenen Sensoren aus.

    :param sensor_data: Dictionary mit den Sensor-Daten.
    :param sensor_status: Dictionary mit den Sensor-Status-Werten.
    """
    print("Sensor-Daten:")
    for key, value in sensor_data.items():
        print(f"{key}: {value}")

    print("\nSensor-Status:")
    for key, value in sensor_status.items():
        print(f"{key}: {value}")

    print("\nÜberprüfung der Sensorstatus:")
    all_ok = True
    for key, value in sensor_status.items():
        if value == 0:
            print(f"Sensor '{key}' hat den Wert 0.")
            all_ok = False

    if all_ok:
        print("Alle Sensorstatus-Werte sind 1.")
    else:
        print("Mindestens ein Sensor hat den Wert 0.")

        
if __name__ == "__main__":
    while True:
        print("-------------------")
        
        _, lokale_Zeit,_ = Zeit_aktualisieren(log_mode="manual")
        sensor_data, sensor_status = read_sensor_data("Manueller_Test",lokale_Zeit, log_mode="manual")
        for key, value in sensor_data.items():
            print(f"{key}: {value}")  

        print("-------------------")
        print("Sensor-Status:")
        print(sensor_status)
        print("-------------------")
        print("Sensor_Daten:")
        print(sensor_data)
    

        
        time.sleep(2)
    