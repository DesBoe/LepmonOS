import os
import csv
from json_read_write import get_value_from_section
from datetime import datetime
from times import *
from logging_utils import *
from fram_operations import read_fram
from sensor_data import *
from hardware import get_device_info

def erstelle_und_aktualisiere_csv(sensor_data, log_mode):
    path = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "general", "current_folder")
    
    csv_name = f"{os.path.basename(path)}.csv"
    csv_path = os.path.join(path, csv_name)

    if log_mode == "manual":
        csv_path = "/home/Ento/Test_sensor_data.csv"
        
    if log_mode == "kamera_test":
        csv_path = os.path.join(path, "Kamera_Testreihe.csv")

    try:
        if not os.path.exists(csv_path) and log_mode == "log":
            print("Erstelle neue CSV Datei und lese Daten für Header")
            Version = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "software", "version")
            try:
                ARNI_Gen = read_fram(0x0130,9)
            except Exception as e:
                ARNI_Gen = get_value_from_section("/home/Ento/serial_number.json", "general", "Fallenversion")
            date = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "software", "date") 
            Strom = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "powermode", "supply")
            
            jetzt_local, lokale_Zeit,_ = Zeit_aktualisieren(log_mode)
            latitude, longitude, _, _, _, _ = get_coordinates()
            
            
            sunset, sunrise, _ = get_sun()
            moonrise, moonset, moon_phase, max_altitude = get_moon(log_mode)
            experiment_start_time, experiment_end_time,_,_ = get_experiment_times()
            
            sensor_id = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "general", "serielnumber")  
            dusk_treshold = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "capture_mode", "dusk_treshold")
            interval = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "capture_mode", "interval")

            sensor = get_device_info("sensor")
            kamera = get_device_info("camera")
            length = get_device_info("length")
            height = get_device_info("height")
            
            with open(csv_path, mode='w', newline='') as csvfile:
                csv_writer = csv.writer(csvfile, delimiter='\t')  # Setze den Tabulator als Trennzeichen
                csv_writer.writerow(["#Machine ID:",                sensor_id])
                csv_writer.writerow(["#Software:",                  f"{Version} vom {date}"])    
                csv_writer.writerow(["ARNI-Generation:",            ARNI_Gen])  
                csv_writer.writerow(["#Kamera:",                    kamera])
                csv_writer.writerow(["#Sensor:",                    sensor])
                csv_writer.writerow(["#Auflösung:",                 f"{length} x {height}"])

                csv_writer.writerow(["#Stromversorgung:",           Strom])         
                csv_writer.writerow([])  
                csv_writer.writerow(["#Experiment Parameter:",])            
                csv_writer.writerow(["#UTC Time:",                  jetzt_local])
                csv_writer.writerow(["#Longitude:",                 longitude]) 
                csv_writer.writerow(["#Latitude:",                  latitude])
                csv_writer.writerow([])
                csv_writer.writerow(["#Sonnenuntergang:",           sunset.strftime("%Y-%m-%d %H:%M:%S")])
                csv_writer.writerow(["#Sonnenaufgang:",             sunrise.strftime("%Y-%m-%d %H:%M:%S")])
                csv_writer.writerow([])
                csv_writer.writerow(["#Mondaufgang:",               moonrise.strftime("%Y-%m-%d %H:%M:%S")])
                csv_writer.writerow(["#Monduntergang:",             moonset.strftime("%Y-%m-%d %H:%M:%S")])
                csv_writer.writerow(["#Mondphase:",                 round(moon_phase, 2)])
                csv_writer.writerow(["#Maximale Kulminationshöhe:", round(max_altitude, 2)])
                csv_writer.writerow([])
                csv_writer.writerow(["#Beginn Monitoring:",         experiment_start_time])
                csv_writer.writerow(["#Ende Monitoring:",           experiment_end_time])
                csv_writer.writerow([])
                csv_writer.writerow(["#Dämmerungs Schwellenwert:",  f"{dusk_treshold} Lux"])
                csv_writer.writerow(["#Aufnahme Intervall:",        f"{interval} min"])
                csv_writer.writerow([])
                csv_writer.writerow(["********************"])
                csv_writer.writerow([])
                csv_writer.writerow(["#Starting new Programme"])
                csv_writer.writerow(["#Local Time:", lokale_Zeit])
                csv_writer.writerow([])

                csv_writer.writerow(sensor_data.keys()) # Schreibe die Überschrift (Keys von sensor_data)
        with open(csv_path, mode='a', newline='') as csvfile:
            csv_writer = csv.writer(csvfile, delimiter='\t')

            if os.path.getsize(csv_path) == 0:
                csv_writer.writerow(sensor_data.keys())

            csv_writer.writerow(sensor_data.values())
            checklist(csv_path, log_mode,algorithm="md5")

    
    except Exception as e:
        error_message(13,e, log_mode)
    
    return csv_path


if __name__ == "__main__":
    read_out=0
    while True:
        read_out +=1
        _, lokale_Zeit,_ = Zeit_aktualisieren(log_mode="manual")
        sensors = read_sensor_data(f"read_out_{read_out}",lokale_Zeit, log_mode="manual")
        csv_path= erstelle_und_aktualisiere_csv(sensors, log_mode="manual")
        print(f"Lese Sensordaten Durchlauf {read_out} und schreibe in {csv_path}")
        time.sleep(5)