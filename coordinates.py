from GPIO_Setup import turn_on_led, turn_off_led, button_pressed
from OLED_panel import *
from json_read_write import *
import time
from service import *
from fram_direct import read_fram, write_fram
from language import get_language

lang = get_language()


def coordinates_in_list(latitude, longitude):
    if latitude / 10 < 1:
        latitude_str = str(latitude).replace('.', '')
        latitude_str = str(0) + latitude_str
    elif latitude / 10 >= 1:
        latitude_str = str(latitude).replace('.', '')
    fehlende_nullen = 9 - len(latitude_str)
    if fehlende_nullen > 0:
        latitude_str = latitude_str + '0' * fehlende_nullen
    latitude_list = [int(x) for x in latitude_str]

    if 0.1 > longitude / 100 >= 0.01:
        longitude_str = str(longitude).replace('.', '')
        longitude_str = str(0) + str(0) + longitude_str
    elif 1 > longitude / 100 >= 0.1:
        longitude_str = str(longitude).replace('.', '')
        longitude_str = str(0) + longitude_str
    elif longitude / 100 >= 1:
        longitude_str = str(longitude).replace('.', '')
    fehlende_nullen = 10 - len(longitude_str)
    if fehlende_nullen > 0:
        longitude_str = longitude_str + '0' * fehlende_nullen
    longitude_list = [int(x) for x in longitude_str]
    return latitude_list, longitude_list        

def is_valid_latitude(latitude_list):
    try:
        lat = float(f"{latitude_list[0]}{latitude_list[1]}.{latitude_list[2]}{latitude_list[3]}{latitude_list[4]}{latitude_list[5]}{latitude_list[6]}{latitude_list[7]}{latitude_list[8]}")
        return -90 <= lat <= 90
    except Exception:
        return False

def is_valid_longitude(longitude_list):
    try:
        lon = float(f"{longitude_list[0]}{longitude_list[1]}{longitude_list[2]}.{longitude_list[3]}{longitude_list[4]}{longitude_list[5]}{longitude_list[6]}{longitude_list[7]}{longitude_list[8]}{longitude_list[9]}")
        return -180 <= lon <= 180
    except Exception:
        return False

def coordinate_input(log_mode):

    latitude_read, longitude_read, pol, block, latitude_ohne_Vorzeichen, longitude_ohne_Vorzeichen = (get_coordinates())

    log_schreiben(f"alte Koordinaten: Breite {latitude_read}, Länge {longitude_read}", log_mode=log_mode)
    print(f"Breite:{latitude_read}")
    print(f"Länge:{longitude_read}")
    show_message("gps_1",lang = lang)
    show_message("gps_2",lang = lang)

    user = False
    nordsued = ""
    while not user:
        turn_on_led("blau")
        if button_pressed("oben"):
            nordsued = "N"
            user = True
            pol = ""
            turn_off_led("blau")
            xpositions_lat = [4,11,21,29,37,45,52,60,68]

        if button_pressed("unten"):
            nordsued = "S"
            user = True
            pol = "-"
            turn_off_led("blau")
            xpositions_lat = [9,15,26,34,41,49,56,64,72]
        else:
            time.sleep(.05)   

    show_message("gps_3",lang = lang)
    user = False
    eastwest = ""
    while not user:
        turn_on_led("blau")
        if button_pressed("oben"):
            eastwest = "E"
            user = True
            block = ""
            turn_off_led("blau")
            xpositions_long = [4,11,18,30,38,45,53,61,69,77]
            time.sleep(1)
        if button_pressed("unten"):
            eastwest = "W"
            user = True
            block = "-"
            turn_off_led("blau")
            xpositions_long = [9,15,23,35,42,49,58,65,73,81]
        else:
            time.sleep(.05)  

    write_value_to_section("/home/Ento/LepmonOS/Lepmon_config.json", "GPS", "Pol", nordsued)     
    write_value_to_section("/home/Ento/LepmonOS/Lepmon_config.json", "GPS", "Block", eastwest) 
    print("saved information on hemisphere in configuration file")
    try:
        write_fram(0x03D0, nordsued.ljust(1))
        write_fram(0x03F0, eastwest.ljust(1))
        print("saved hemisphere in FRAM")
    except Exception as e:
        pass    

    latitude_list, longitude_list = coordinates_in_list(latitude_ohne_Vorzeichen, longitude_ohne_Vorzeichen)

    aktuelle_position = 0
    Wahlmodus = 1
    first_run_1 = True
    first_run_2 = True
    
    while True:
        turn_on_led("blau")
        if first_run_1:
            time.sleep(1)
            first_run_1 = False
        if Wahlmodus == 1:

            x_position = xpositions_lat[aktuelle_position]
            show_message_with_arrows(
                "gps_4",
                lang=lang,
                Breite=f"{pol}{latitude_list[0]}{latitude_list[1]}.{latitude_list[2]}{latitude_list[3]}{latitude_list[4]}{latitude_list[5]}{latitude_list[6]}{latitude_list[7]}{latitude_list[8]}",
                x_position=x_position)

        if Wahlmodus == 2:
            if first_run_2:
                time.sleep(1)
                first_run_2 = False

            x_position = xpositions_long[aktuelle_position]
            show_message_with_arrows(
                "gps_5",
                lang=lang,
                Länge=f"{block}{longitude_list[0]}{longitude_list[1]}{longitude_list[2]}.{longitude_list[3]}{longitude_list[4]}{longitude_list[5]}{longitude_list[6]}{longitude_list[7]}{longitude_list[8]}{longitude_list[9]}",
                x_position=x_position)


        if button_pressed("oben"):
            if Wahlmodus == 1:
                latitude_list[aktuelle_position] = (latitude_list[aktuelle_position] + 1) % 10
                if not is_valid_latitude(latitude_list):
                    latitude_list[aktuelle_position] = (latitude_list[aktuelle_position] - 1) % 10
                    show_message("gps_6", lang = lang)
            if Wahlmodus == 2:
                longitude_list[aktuelle_position] = (longitude_list[aktuelle_position] + 1) % 10
                if not is_valid_longitude(longitude_list):
                    longitude_list[aktuelle_position] = (longitude_list[aktuelle_position] - 1) % 10
                    show_message("gps_7", lang = lang)

        if button_pressed("unten"):
            if Wahlmodus == 1:
                latitude_list[aktuelle_position] = (latitude_list[aktuelle_position] - 1) % 10
                if not is_valid_latitude(latitude_list):
                    latitude_list[aktuelle_position] = (latitude_list[aktuelle_position] + 1) % 10
                    show_message("gps_6", lang = lang)
            if Wahlmodus == 2:
                longitude_list[aktuelle_position] = (longitude_list[aktuelle_position] - 1) % 10
                if not is_valid_longitude(longitude_list):
                    longitude_list[aktuelle_position] = (longitude_list[aktuelle_position] + 1) % 10
                    show_message("gps_7", lang = lang)

        if button_pressed("rechts"):
            if Wahlmodus == 1:
                aktuelle_position = (aktuelle_position + 1) % 9
            if Wahlmodus == 2:
                aktuelle_position = (aktuelle_position + 1) % 10

        if button_pressed("enter"):
            Wahlmodus += 1
            aktuelle_position = 0 
        
        if Wahlmodus == 3:
            turn_off_led("blau")
            break  
        time.sleep(0.05)

    latitude_write = float(f"{latitude_list[0]}{latitude_list[1]}.{latitude_list[2]}{latitude_list[3]}{latitude_list[4]}{latitude_list[5]}{latitude_list[6]}{latitude_list[7]}{latitude_list[8]}")
    longitude_write = float(f"{longitude_list[0]}{longitude_list[1]}{longitude_list[2]}.{longitude_list[3]}{longitude_list[4]}{longitude_list[5]}{longitude_list[6]}{longitude_list[7]}{longitude_list[8]}{longitude_list[9]}")

    return latitude_write, longitude_write, latitude_read, longitude_read

def set_coordinates(log_mode):
    """
    Fordert den Nutzer so lange zur Eingabe auf, bis gültige Koordinaten eingegeben wurden.
    Gibt die gültigen Koordinaten zurück.
    """
    while True:
        latitude_write, longitude_write, latitude_read, longitude_read = coordinate_input(log_mode)
        if -90 <= latitude_write <= 90 and -180 <= longitude_write <= 180:
            print(f"Breite_alt:{latitude_read}")
            print(f"Breite_neu:{latitude_write}")    
            print(f"Länge_alt:{longitude_read}")
            print(f"Länge_neu:{longitude_write}")    
            if latitude_write == latitude_read:
                print("Breite unverändert")
                log_schreiben(f"Breite unverändert", log_mode=log_mode)
            if longitude_write == longitude_read:
                print("Länge unverändert")     
                log_schreiben(f"Länge unverändert", log_mode=log_mode) 
            # Prüfen, ob sich die Koordinaten geändert haben
            write_value_to_section("/home/Ento/LepmonOS/Lepmon_config.json", "GPS", "latitude", latitude_write)     
            write_value_to_section("/home/Ento/LepmonOS/Lepmon_config.json", "GPS", "longitude", longitude_write)            
            if latitude_write != latitude_read or longitude_write != longitude_read:
                log_schreiben(f"neue Koordinaten: Breite {latitude_write}, Länge {longitude_write}", log_mode=log_mode)
                try:
                    lat_fram = str(latitude_write).ljust(9)
                    long_fram = str(longitude_write).ljust(10)
                 
                    write_fram(0x03C0, lat_fram)
                    write_fram(0x03E0, long_fram)
                except:
                    pass       
                log_schreiben(f"neue Koordinaten wurden gespeichert", log_mode=log_mode)
                print("saved GPS coordinates in configuration file and FRAM")
                show_message("gps_8",lang = lang)

            break          
        else:
            show_message("gps_9",lang = lang)
    time.sleep(.5)      

if __name__ == "__main__":
    print("Setze GPS Koordinaten mit dem lokalen Button Interface")
    set_coordinates(log_mode="manual")