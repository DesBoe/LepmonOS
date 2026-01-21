from OLED_panel import show_message
from Camera import get_frame
from GPIO_Setup import button_pressed
import time
from datetime import datetime, timedelta
import cv2
from logging_utils import *
import sys
from Lights import *
from end import trap_shutdown
from GPIO_Setup import *
import numpy as np
from language import get_language
from gpiozero import LED
from json_read_write import get_value_from_section
from image_quality_check import *


def focus(log_mode):
    lang = get_language()
    
    image_exposure_is_good = False
    camera = LED(5)
    camera.on()
    Exposure = 140
    Gain = 5
    variance_old = -1
    variance_new, variance_display, FokusFehler  = 0,0,0
    average_brightness = "   "
    image_over,image_under = False, False
    brightness_reference = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","image_quality","brightness_reference")

    print("Fokusieren:\n"
          "ARNI berechnet den schärfsten Fokus, basierend auf der 'Variance of Laplacian'\n" 
          "siehe https://pyimagesearch.com/2015/09/07/blur-detection-with-opencv/\n"
          "Fokusring drehen, bis der Schärfewert im Display sein Maximum erreicht hat")
    if read_fram_bytes(0x078F, 1) == b'\x01':
        log_schreiben("Verstecktes Menü und Fokusieren erzwungen, da das Fokusieren im letzten Versuch nicht erfolgreich war", log_mode=log_mode)
    write_fram_bytes(0x078F, b'\x01') # Vermerk, dass das Menü geöffnet wurde. Beenden schreibt wieder die Null
    time.sleep(3)
    dim_up()
    vis_start = datetime.now()
    vis_emergency = vis_start + timedelta(minutes=5) 
    turn_on_led("blau")
    while not image_exposure_is_good:
        now = datetime.now()
        print(f"aktuelle Zeit:{now}")
        if vis_emergency <= now:
            dim_down()
            show_message("focus_12", lang = lang)
            print("Notfallabschaltung Visible LED")
            return
            
        show_message("focus_1", lang = lang, average_brightness = average_brightness, Exposure = Exposure, Gain = Gain)
        turn_on_led("gelb")
        result,_,_ = get_frame(Exposure, "focus", log_mode, Gain)
        turn_off_led("gelb")
        
        if isinstance(result, tuple):
            frame = result[0]
        else:
            frame = result
        if frame is not None and isinstance(frame, (np.ndarray,)):
            FokusFehler = 0
        else:
            FokusFehler += 1
            print("Fokussier fehler")
            
            
        if FokusFehler >= 4:
            error_message(2, "Kamera mehrfach beim Fokussieren nicht initialisiert. ARNI startet neu", log_mode=log_mode)
            show_message("focus_2", lang = lang)
            show_message("focus_3", lang = lang)
            trap_shutdown(log_mode, 5)

        print("Belichtungs Analyse")
        
        if FokusFehler == 0 and frame is not None and isinstance(frame, (np.ndarray,)):
            print("image_over:", image_over, " image_under:", image_under)
            try:
                average_brightness, Exposure, Gain, image_exposure_is_good = calculate_Exposure_and_gain(frame, Exposure, Gain, log_mode)
                if average_brightness > brightness_reference:
                    print("average_brightness:", average_brightness, " > brightness_reference:", brightness_reference)
                    image_over = True
                    print(image_over)
                if average_brightness < brightness_reference:
                    print("average_brightness:", average_brightness, " < brightness_reference:", brightness_reference)
                    image_under = True
                    print(image_under)
                if image_over and image_under:
                    print("Bildbelichtung ist gut")
                    image_exposure_is_good = True
                    break

            except Exception as e:
                print(f"Fehler bei der Bildanalyse: {e}")
    
        turn_on_led("gelb")
        for _ in range(25):
            if button_pressed("enter"):
                print("Belichtung manuel gesetzt vom Benutzer")
                break
            time.sleep(0.01)
            turn_off_led("gelb")
    
    show_message("focus_4", lang = lang)
    show_message("focus_5", lang = lang)
            
            
            
    print("--------------------------Fokus Start--------------------------")
        
    while True:
            now = datetime.now()
            print(f"aktuelle Zeit:{now}")
            if vis_emergency <= now:
                dim_down()
                show_message("focus_12", lang = lang)
                print("Notfallabschaltung Visible LED")
                return
            turn_on_led("blau")
            if variance_old < 0:
                show_message("focus_6", lang= lang, variance_old="  ", variance_new=" ")
            elif variance_old >= 0:
                show_message("focus_6", lang= lang, variance_old=variance_old, variance_new=variance_display)
            turn_off_led("blau")
            show_message("focus_7", lang= lang, variance_old=variance_old, variance_new=variance_display)
            turn_on_led("gelb")
            result,_ ,_ = get_frame(Exposure, "focus", log_mode,Gain)
            turn_off_led("gelb")
            if isinstance(result, tuple):
                frame = result[0]
            else:
                frame = result
            if frame is not None and isinstance(frame, (np.ndarray,)):
                FokusFehler = 0
            else:
                FokusFehler += 1
                print("Fokussier fehler")
                
                
            if FokusFehler >= 4:
                error_message(2, "Kamera mehrfach beim Fokussieren nicht initialisiert. ARNI startet neu", log_mode=log_mode)
                show_message("focus_2", lang = lang)
                show_message("focus_3", lang = lang)
                log_schreiben("Kamera mehrfach beim Fokussieren nicht initialisiert", log_mode=log_mode)
                #write_fram_bytes(0x078F, b'\x01')
                log_schreiben("##################################", log_mode=log_mode)
                log_schreiben("### SELBSTINDUZIERTER SHUTDOWN ###", log_mode=log_mode)
                log_schreiben("##################################", log_mode=log_mode)
                trap_shutdown(log_mode, 5)

            print("Schärfe Analyse")
            if FokusFehler == 0 and frame is not None and isinstance(frame, (np.ndarray,)):
                
                try:
                    _, variance = check_focus(frame)
                    variance_display = round(variance, 0)
                    variance_new = variance_display +.0000001
                    if variance_old > 0:
                        if variance > variance_old:
                            show_message("focus_8", lang = lang, variance_old=variance_old, variance_new=variance_display)
                            print(f"schärfer - weiter drehen: neu {variance_new} -- alt {variance_old}")
                        elif variance < variance_old:
                            show_message("focus_9", lang = lang, variance_old=variance_old, variance_new=variance_display)
                            print(f"unschärfer - zurück drehen: neu {variance_new} -- alt {variance_old}")
                        elif variance == variance_old:
                            show_message("focus_10", lang = lang, variance_old=variance_old, variance_new=variance_display)
                            print(f"gleichbleibend - keine Änderung: neu {variance_new} -- alt {variance_old}")
                        else:
                            print(f"Fehler bei der Schärfewert Analyse")
                    variance_old = round(variance, 0)
                    
                    turn_on_led("gelb")
                    for _ in range(25):
                        if button_pressed("enter"):
                            show_message("focus_11", lang = lang)
                            print("Fokusieren beendet vom Benutzer")
                            write_fram_bytes(0x078F, b'\x00')
                            log_schreiben(f"Fokus gefunden mit Schärfewert: {variance_old}", log_mode=log_mode)
                            log_schreiben("Fokussieren beendet", log_mode=log_mode)
                            dim_down()
                            return
                    time.sleep(0.01)
                    turn_off_led("gelb")
                    
                except Exception as e:
                    print(f"Fehler bei der Schärfeanalyse: {e}")  
            
                    
if __name__ == "__main__":
    focus("manual")
            
        
            