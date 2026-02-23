import time
from datetime import datetime
from GPIO_Setup import turn_on_led, turn_off_led, button_pressed
from OLED_panel import *
import adafruit_ds3231
from logging_utils import log_schreiben, error_message
import subprocess
import board
from service import RPI_time
from language import get_language

lang = get_language()
x_positions = [4,10,18,25,40,47,59,66,4,10,22,28,40,46]
def input_time(log_mode):
    print("Bitte Uhrzeit der Hardware Uhr Stellen")
    rtc_status = False
    try:
        i2c = board.I2C()
        rtc = adafruit_ds3231.DS3231(i2c)
        rtc_status = True

    except Exception as e:
        error_message(8, e, log_mode)
        # Fallback: Default-Werte
        date_time_list = [2,0,2,4,0,1,0,1,0,0,0,0,0,0]    
    if rtc_status:

        t = rtc.datetime
        time_string = f"{t.tm_year:04d}-{t.tm_mon:02d}-{t.tm_mday:02d} {t.tm_hour:02d}:{t.tm_min:02d}:{t.tm_sec:02d}"
        print(f"Aktuelle Hardware Uhrzeit: {time_string}")
        date_time_list = [int(digit) for digit in time_string if digit.isdigit()]
        print(f"Liste:{date_time_list}")

    aktuelle_position = 0
    Wahlmodus = 1  
    first_run = True  

    while True:
        turn_on_led("blau")
        
        if Wahlmodus == 1:
            '''
            if aktuelle_position < 4:
                positionszeiger_date = "_" * aktuelle_position
            elif 4 <= aktuelle_position < 6:
                positionszeiger_date = "_"*4 + "-" +"_" * (aktuelle_position-4)
            elif aktuelle_position >= 6:
                positionszeiger_date = "_"*4 + "-" + "_" *2 + "-" + "_" * (aktuelle_position-6)
            positionszeiger_date += "x"
            pos_date = positionszeiger_date.find("x")
            positionszeiger_date_dunkel = positionszeiger_date[:pos_date]
            positionszeiger_date_hell = positionszeiger_date[pos_date]  # Das ist das 'x'
            '''
            x_position = x_positions[aktuelle_position]
            show_message_with_arrows("rtc_1",
                                     lang= lang, 
                                     date = f"{date_time_list[0]}{date_time_list[1]}{date_time_list[2]}{date_time_list[3]}-{date_time_list[4]}{date_time_list[5]}-{date_time_list[6]}{date_time_list[7]}",
                                      x_position=x_position)

        elif Wahlmodus == 2:
            if first_run:
                time.sleep(1)
                first_run = False
            '''
            if 8 <= aktuelle_position <10:
                positionszeiger_time = "_" * (aktuelle_position-8)
            elif 10 <= aktuelle_position < 12:
                positionszeiger_time = "__:" + "_" * (aktuelle_position-10)
            elif aktuelle_position >=12 :
                positionszeiger_time = "__:__" + ":" + "_" * (aktuelle_position-12)
            positionszeiger_time += "x"
            pos_time = positionszeiger_time.find("x")
            positionszeiger_time_dunkel = positionszeiger_time[:pos_time]
            positionszeiger_time_hell = positionszeiger_time[pos_time]  # Das ist das 'x'
            '''
            x_position = x_positions[aktuelle_position]
            show_message_with_arrows("rtc_2",
                                        lang= lang, 
                                        time = f"{date_time_list[8]}{date_time_list[9]}:{date_time_list[10]}{date_time_list[11]}:{date_time_list[12]}{date_time_list[13]}",
                                         x_position=x_position)
            
        if button_pressed("oben"):

            if aktuelle_position == 4:  # Monat Zehnerstelle (max 1)
                date_time_list[4] = (date_time_list[4] + 1) % 2
                if date_time_list[4] == 1 and date_time_list[5] > 2:
                    date_time_list[5] = 2
            elif aktuelle_position == 5:  # Monat Einerstelle (max 9 oder 2)
                max_einer = 2 if date_time_list[4] == 1 else 9
                date_time_list[5] = (date_time_list[5] + 1) % (max_einer + 1)
            elif aktuelle_position == 6:  # Tag Zehnerstelle (max 3)
                date_time_list[6] = (date_time_list[6] + 1) % 4
                if date_time_list[6] == 3 and date_time_list[7] > 1:
                    date_time_list[7] = 1
            elif aktuelle_position == 7:  # Tag Einerstelle (max 9 oder 1)
                max_einer = 1 if date_time_list[6] == 3 else 9
                date_time_list[7] = (date_time_list[7] + 1) % (max_einer + 1)
            elif aktuelle_position == 8:  # Stunde Zehnerstelle (max 2)
                date_time_list[8] = (date_time_list[8] + 1) % 3
                if date_time_list[8] == 2 and date_time_list[9] > 3:
                    date_time_list[9] = 3
            elif aktuelle_position == 9:  # Stunde Einerstelle (max 9 oder 3)
                max_einer = 3 if date_time_list[8] == 2 else 9
                date_time_list[9] = (date_time_list[9] + 1) % (max_einer + 1)
            elif aktuelle_position == 10:  # Minute Zehnerstelle (max 5)
                date_time_list[10] = (date_time_list[10] + 1) % 6
            elif aktuelle_position == 11:  # Minute Einerstelle (max 9)
                date_time_list[11] = (date_time_list[11] + 1) % 10
            elif aktuelle_position == 12:  # Sekunde Zehnerstelle (max 5)
                date_time_list[12] = (date_time_list[12] + 1) % 6
            elif aktuelle_position == 13:  # Sekunde Einerstelle (max 9)
                date_time_list[13] = (date_time_list[13] + 1) % 10
            else:
                date_time_list[aktuelle_position] = (date_time_list[aktuelle_position] + 1) % 10

        elif button_pressed("unten"):
            # Begrenzung je nach Position
            if aktuelle_position == 4:  # Monat Zehnerstelle (max 1)
                date_time_list[4] = (date_time_list[4] - 1) % 2
                if date_time_list[4] == 1 and date_time_list[5] > 2:
                    date_time_list[5] = 2
            elif aktuelle_position == 5:  # Monat Einerstelle (max 9 oder 2)
                max_einer = 2 if date_time_list[4] == 1 else 9
                date_time_list[5] = (date_time_list[5] - 1) % (max_einer + 1)
            elif aktuelle_position == 6:  # Tag Zehnerstelle (max 3)
                date_time_list[6] = (date_time_list[6] - 1) % 4
                if date_time_list[6] == 3 and date_time_list[7] > 1:
                    date_time_list[7] = 1
            elif aktuelle_position == 7:  # Tag Einerstelle (max 9 oder 1)
                max_einer = 1 if date_time_list[6] == 3 else 9
                date_time_list[7] = (date_time_list[7] - 1) % (max_einer + 1)
            elif aktuelle_position == 8:  # Stunde Zehnerstelle (max 2)
                date_time_list[8] = (date_time_list[8] - 1) % 3
                if date_time_list[8] == 2 and date_time_list[9] > 3:
                    date_time_list[9] = 3
            elif aktuelle_position == 9:  # Stunde Einerstelle (max 9 oder 3)
                max_einer = 3 if date_time_list[8] == 2 else 9
                date_time_list[9] = (date_time_list[9] - 1) % (max_einer + 1)
            elif aktuelle_position == 10:  # Minute Zehnerstelle (max 5)
                date_time_list[10] = (date_time_list[10] - 1) % 6
            elif aktuelle_position == 11:  # Minute Einerstelle (max 9)
                date_time_list[11] = (date_time_list[11] - 1) % 10
            elif aktuelle_position == 12:  # Sekunde Zehnerstelle (max 5)
                date_time_list[12] = (date_time_list[12] - 1) % 6
            elif aktuelle_position == 13:  # Sekunde Einerstelle (max 9)
                date_time_list[13] = (date_time_list[13] - 1) % 10
            else:
                date_time_list[aktuelle_position] = (date_time_list[aktuelle_position] - 1) % 10

        elif button_pressed("rechts"):
            if Wahlmodus == 1:
                aktuelle_position = (aktuelle_position + 1) % 8
            elif Wahlmodus == 2:
                if aktuelle_position != 13:
                    aktuelle_position = (aktuelle_position + 1) % 14
                else:
                    aktuelle_position = 8

        elif button_pressed("enter"):
            Wahlmodus += 1
            aktuelle_position = 8
            show_message("blank", lang = lang)

        elif Wahlmodus >= 3:
            turn_off_led("blau")
            print("zeitbefehl erstellt")
            break

        time.sleep(0.05)  # Kurze Pause für die Stabilität
    turn_off_led("blau")    

    # Construct the command for setting system time
    system_time_str = f"{date_time_list[0]}{date_time_list[1]}{date_time_list[2]}{date_time_list[3]}-{date_time_list[4]}{date_time_list[5]}-{date_time_list[6]}{date_time_list[7]} {date_time_list[8]}{date_time_list[9]}:{date_time_list[10]}{date_time_list[11]}:{date_time_list[12]}{date_time_list[13]}"
    print("Eingegebener Zeitsring:", system_time_str)
    
    # Validierung der Eingabewerte
    jahr = int(f"{date_time_list[0]}{date_time_list[1]}{date_time_list[2]}{date_time_list[3]}")
    monat = int(f"{date_time_list[4]}{date_time_list[5]}")
    tag = int(f"{date_time_list[6]}{date_time_list[7]}")
    stunde = int(f"{date_time_list[8]}{date_time_list[9]}")
    minute = int(f"{date_time_list[10]}{date_time_list[11]}")
    sekunde = int(f"{date_time_list[12]}{date_time_list[13]}")
    return jahr, monat, tag, stunde, minute, sekunde, date_time_list

def check_date_time(log_mode):
    jahr, monat, tag, stunde, minute, sekunde, _ = input_time(log_mode)
    try:
        # Jahr prüfen
        if not (2025 <= jahr <= 2035):
            show_message("rtc_3", lang = lang)     
            return False
        # Monat prüfen
        if not (1 <= monat <= 12):
            show_message("rtc_4", lang = lang)
            return False
        # Tag prüfen (einfach, ohne Monatslänge/Schaltjahr)
        if not (1 <= tag <= 31):
            show_message("rtc_5", lang = lang)
            return False
        # Stunde prüfen
        if not (0 <= stunde <= 23):
            show_message("rtc_6", lang = lang)
            return False
        # Minute prüfen
        if not (0 <= minute <= 59):
            show_message("rtc_7", lang = lang)
            return False
        # Sekunde prüfen
        if not (0 <= sekunde <= 59):
            show_message("rtc_8", lang = lang)
            return False
        # Optional: exakte Prüfung mit datetime (inkl. Monatslänge/Schaltjahr)
        datetime(jahr, monat, tag, stunde, minute, sekunde)
        return True
    except Exception:
        return False    
    
def set_hwc(rtc_mode, log_mode, date_time_list=None, ):
    if rtc_mode == "hmi":
        _, _, _, _, _, _, date_time_list = input_time(log_mode)
    
    if rtc_mode == "manual":
        date_time_list = date_time_list
        date_time_list = [int(char) for char in date_time_list if char.isdigit()]
    
    if rtc_mode == "daylight_saving":
        date_time_list = date_time_list
        print("Automatische Umstellung auf Sommerzeit/Winterzeit")
        print(f"Eingegebene Zeitliste: {date_time_list}")
        time.sleep(1)
    rtc_status = False
    while True:
        # Werte extrahieren
        jahr = int(f"{date_time_list[0]}{date_time_list[1]}{date_time_list[2]}{date_time_list[3]}")
        monat = int(f"{date_time_list[4]}{date_time_list[5]}")
        tag = int(f"{date_time_list[6]}{date_time_list[7]}")
        stunde = int(f"{date_time_list[8]}{date_time_list[9]}")
        minute = int(f"{date_time_list[10]}{date_time_list[11]}")
        sekunde = int(f"{date_time_list[12]}{date_time_list[13]}")
        # Prüfe Werte vor dem Setzen!
        if not (2000 <= jahr <= 2099 and 1 <= monat <= 12 and 1 <= tag <= 31 and 0 <= stunde <= 23 and 0 <= minute <= 59 and 0 <= sekunde <= 59):
            show_message("rtc_9", lang = lang)
            print("Ungültige Eingabe, bitte erneut versuchen.")
            _, _, _, _, _, _, date_time_list = input_time(log_mode)
            continue
        try:
            i2c = board.I2C()
            rtc = adafruit_ds3231.DS3231(i2c)
            rtc_status = True
        except Exception as e:
            error_message(8, e, log_mode)
            show_message("err_08", lang = lang)
        if rtc_status:                               
            rtc_time = time.struct_time((
                jahr, monat, tag, stunde, minute, sekunde,
                0,  # weekday (ignored by DS3231)
                -1, -1  # yearday, isdst (ignored)
            ))
            print("RTC wird gesetzt auf Systemzeit:", rtc_time)
            rtc.datetime = rtc_time
            RPI_time(log_mode)
            log_schreiben(f"Hardware Uhrzeit gesetzt auf: {rtc_time.tm_year}-{rtc_time.tm_mon:02d}-{rtc_time.tm_mday:02d} {rtc_time.tm_hour:02d}:{rtc_time.tm_min:02d}:{rtc_time.tm_sec:02d}", log_mode=log_mode)
            break
        if not rtc_status:
            
            # Construct the command RPi internal time
            system_time_str = f"{date_time_list[0]}{date_time_list[1]}{date_time_list[2]}{date_time_list[3]}-{date_time_list[4]}{date_time_list[5]}-{date_time_list[6]}{date_time_list[7]} {date_time_list[8]}{date_time_list[9]}:{date_time_list[10]}{date_time_list[11]}:{date_time_list[12]}{date_time_list[13]}"
            print("Eingegebener Zeitsring:", system_time_str)
    
            subprocess.run(["sudo", "date", "-s", system_time_str], check=True)
            log_schreiben(f"Harware Uhr konnte nicht gestellt werden. setze Uhrzeit des Raspberry auf:{date_time_list}", log_mode=log_mode)
            print(f"Raspberry Pi Systemzeit gesetzt auf: {system_time_str}")
            show_message("rtc_10", lang = lang)
            break

            _, _, _, _, _, _, date_time_list = input_time()
    time.sleep(0.5)

if __name__ == "__main__":
        ################
        # time string # 
        ################
                            #"JJJJMMTTSSMMHH"
        date_time_list =     "20260223182600"  

        if len(date_time_list) != 14 or not date_time_list.isdigit():
            print("Fehler: Die Eingabe muss genau 14 Ziffern enthalten und nur Ziffern!")
            exit()
        else:
            set_hwc(rtc_mode="manual", log_mode="manual", date_time_list=date_time_list)