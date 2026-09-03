from vmbpy import *
from Lights import *
from json_read_write import *
import time
from datetime import datetime
import os
import cv2
from OLED_panel import *
from logging_utils import log_schreiben
from GPIO_Setup import *
from gpiozero import LED
from sensor_data import get_power
from logging_utils import *

from service import *
from runtime import write_timestamp
from image_quality_check import *
import numpy as np
import gc
from hardware import get_hardware_version, get_device_info
from dev_mode import DEV_MODE, note_mock
from mock_hardware import generate_mock_frame

from flatfield import load_flatfield, apply_flatfield

lang = get_language()


Skip_Sanity_Check = False
# Danger Zone: Skip_Sanity_Check should only be used within enabled Experiment_Interval!
# Check Lepmon_config.json for "Skip_Sanity_Check" in "Experiment_Interval" section.

Enable_Interval = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "Experiment_Interval", "Enable_Interval")

if get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "Experiment_Interval", "Enable_Interval"):
    Skip_Sanity_Check = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "Experiment_Interval", "Skip_Sanity_Check")
    print("ACHTUNG: Skip_Sanity_Check ist aktiviert. Bilder werden nicht auf Schwarze Pixel geprüft.")
    


# Kamera GPIO Pin
camera = LED(5)


def _av_camera_present():
    """Cheap presence check - lists cameras without opening/configuring one."""
    try:
        with VmbSystem.get_instance() as vmb:
            return bool(vmb.get_all_cameras())
    except Exception:
        return False

def av_camera_available(cam_Initiliase_tries, log_mode):
    try:
        with VmbSystem.get_instance() as vmb:
            cameras = vmb.get_all_cameras()
            if cameras:
                print(f"Allied-Vision-Kamera gefunden: {cameras[0].get_id()}")
                return True
            if cam_Initiliase_tries > 10:    
                print("Keine Allied-Vision-Kamera gefunden.")
            return False

    except Exception as error:
        message = f"Vimba X konnte nicht gestartet werden: {error}"
        print(message)
        log_schreiben(message, log_mode=log_mode)
        return False
    
HARDWARE_VERSION = get_hardware_version()

# check for corrections that should be applied to the image based on the configuration file and load corresponding values or use default
gamma_correction = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "capture_mode", "gamma_correction")
if gamma_correction:
    gamma = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "AV__Alvium_1800_U-2050", "gamma_value")
else:
    gamma = 1

adjust_ContrastShape = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "capture_mode", "adjust_ContrastShape")
if adjust_ContrastShape:
    ContrastShape = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "AV__Alvium_1800_U-2050", "ContrastShape") 
else:
    ContrastShape = 4 # default value. This value was used before introduction of the ContrastShape parameter in the configuration file.




# --- Flatfield-Korrektur ---------------------------------------------------
# Laedt einmalig das 16-bit-TIF-Flatfield und korrigiert jeden aufgenommenen
# Frame, bevor er gespeichert wird. Schlaegt etwas fehl, wird der Frame
# unveraendert durchgereicht (die naechtliche Aufnahme darf nie scheitern).
flatfield_correction = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "capture_mode", "flatfield_correction")
if flatfield_correction:
    if HARDWARE_VERSION in ["Pro_Gen_1", "Pro_Gen_2"]:
        FLATFIELD_TIF = "/home/Ento/LepmonOS/flatfield_masks/flatfield_divisor_16bit_Pro_Gen_1_2.tif"
    elif HARDWARE_VERSION in ["Pro_Gen_3"]:
        FLATFIELD_TIF = "/home/Ento/LepmonOS/flatfield_divisor_16bit_Pro_Gen_3.tif"
    elif HARDWARE_VERSION in ["Pro_Gen_4"]:
        FLATFIELD_TIF = "/home/Ento/LepmonOS/flatfield_masks/flatfield_divisor_16bit_Pro_Gen_4.tif"
    
    def _load_flat(log_mode="manual"):
        # log_mode defaults to "manual" (console-only): this runs at module
        # import time, before erstelle_ordner()/initialisiere_logfile() has
        # necessarily created a session log file, so log_mode="log" here would
        # retry against a possibly-missing path and could trigger a forced
        # reboot (see log_schreiben) on every import.
        try:
            flat = load_flatfield(FLATFIELD_TIF)
            if flat is None:
                log_schreiben(f"Flatfield nicht ladbar, Korrektur deaktiviert: {FLATFIELD_TIF}", log_mode=log_mode)
            else:
                log_schreiben(f"Flatfield geladen ({flat.shape[1]}x{flat.shape[0]}), Korrektur aktiv.", log_mode=log_mode)
            return flat
        except Exception as e:
            log_schreiben(f"Fehler beim Laden des Flatfields: {e}", log_mode=log_mode)
            return None

    _FLAT = _load_flat()
elif not flatfield_correction:
    _FLAT = None
    log_schreiben("Flatfield Korrektur für AV Kamera deaktiviert.", log_mode="manual")



# ---Testschalter VmbError---------------------------------------------------
# Testschalter: mit FORCE_LOAD_SETTINGS_ERROR=1 wird cam.load_settings() erzwungen. Aufruf im Terminal:
#     
# FORCE_LOAD_SETTINGS_ERROR=1 python Camera_AV.py
# FORCE_LOAD_SETTINGS_ERROR=1 python capturing.py
#    
# # mit VmbError.RetriesExceeded fehlschlagen, um den Fehlerpfad zu pruefen.
if os.environ.get("FORCE_LOAD_SETTINGS_ERROR") == "1":
    def _forced_load_settings_error(*_args, **_kwargs):
        raise RuntimeError("RetriesExceeded (simuliert)")
    Camera.load_settings = _forced_load_settings_error
    print("###############################################################################################")
    print("#ACHTUNG: FORCE_LOAD_SETTINGS_ERROR aktiv - erzwinge Fehler beim Laden der Kameraeinstellungen#")
    print("###############################################################################################")
    time.sleep(2)



def get_frame_AV(Exposure, cam_mode, log_mode, Gain, gamma=1, ContrastShape = 4):
    cams = None
    cam_Initiliase_tries = 0
    power_vis = "---"
    frame = None
    Kamera_Status = 0
    error_details = ""

    if DEV_MODE and not _av_camera_present():
        note_mock("Allied Vision camera (vmbpy)")
        frame = generate_mock_frame(get_device_info('length'), get_device_info('height'), label="DEV MODE - AV")
        try:
            _, _, _, power_vis, _ = get_power()
        except Exception:
            power_vis = "---"
        return frame, 1, power_vis

    if cam_mode == "display":
        show_message("cam_1", lang=lang)
    while not av_camera_available(cam_Initiliase_tries, log_mode):
        cam_Initiliase_tries += 1
        time.sleep(0.1)
        if cam_Initiliase_tries > 100:
            print(f"Kamera nach {cam_Initiliase_tries} Versuchen nicht initalisiert")
            log_schreiben(f"Kamera nach {cam_Initiliase_tries} Versuchen nicht initalisiert", log_mode=log_mode)
            show_message("cam_3", lang=lang)
            time.sleep(5)
            if error_details == "":
                error_details = f"Kamera nach {cam_Initiliase_tries} Versuchen nicht initalisiert"
    
            error_message(1, error_details, log_mode)
            log_schreiben(f"Fehler beim Abrufen des Frames: {error_details}",log_mode=log_mode)
            print("Prüfe Kamera Verbindung und Stromversorgung")
            break
    print(f"Kamera nach {cam_Initiliase_tries} Versuchen gefunden, Versuche frame aquisition")
    #if _av_camera_present():
    try:
            with VmbSystem.get_instance() as vmb:
                cams = vmb.get_all_cameras()
                if not cams:
                    log_schreiben("Keine Kamera gefunden (vmbpy).", log_mode=log_mode)
                    raise RuntimeError("Keine Kamera gefunden (vmbpy).")

                with cams[0] as cam:
                    print(f"Verwende gefundene Kamera:{cam}")
                    settings_file = "/home/Ento/LepmonOS/Kamera_Einstellungen_VimbaX.xml".format(cam.get_id()) 

                    try:
                        print("lade Kameraeinstellungen")
                        cam.load_settings(settings_file, PersistType.All)
                        print("Kameraeinstellungen erfolgreich geladen")
                        time.sleep(.1)
                    except Exception as e:
                        log_schreiben(f"Fehler beim Laden der Kameraeinstellungen: {e}", log_mode=log_mode)
                        raise RuntimeError(f"Fehler beim Laden der Kameraeinstellungen: {e}")
                    
                    try:
                        cam.ExposureTime.set(Exposure * 1000)
                        print(f"Exposure in Kamera Einstellungen geändert:{(cam.ExposureTime.get()/1000):.0f}")
                    except Exception as e:
                        log_schreiben(f"Fehler beim Setzen der Belichtungszeit: {e}", log_mode=log_mode)
                        
                    try:
                        cam.Gain.set(Gain)
                        print(f"Gain in Kamera Einstellungen geändert:{cam.Gain.get()}")
                    except Exception as e:
                        log_schreiben("Fehler beim Setzen des Gains: {e}", log_mode=log_mode)

                    try:
                        cam.Gamma.set(gamma)
                        print(f"Gamma in Kamera Einstellungen geändert:{cam.Gamma.get()}")
                    except Exception as e:
                        log_schreiben(f"Fehler beim Setzen von Gamma: {e}", log_mode=log_mode)

                    try:
                        cam.ContrastShape.set(ContrastShape)
                        print(f"ContrastShape in Kamera Einstellungen geändert:{cam.ContrastShape.get()}")
                    except Exception as e:
                        log_schreiben(f"Fehler beim Setzen von ContrastShape: {e}", log_mode=log_mode)

                    try:
                        print(f"Pixelformat der Kamera: {cam.get_pixel_format()}")
                    except Exception as e:
                        log_schreiben(f"unbekanntes Pixelformat:{e}", log_mode=log_mode)

                    if cam_mode != "display":
                        red_balance = float(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "AV__Alvium_1800_U-2050", "balance_ratio_red"))
                        blue_balance = float(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "AV__Alvium_1800_U-2050", "balance_ratio_blue"))
                        try:
                            cam.BalanceRatioSelector.set("Red")
                            cam.BalanceRatio.set(red_balance)
                            print(f"Red Balance in Kamera Einstellungen geändert:{cam.BalanceRatio.get()}")

                            cam.BalanceRatioSelector.set("Blue")
                            cam.BalanceRatio.set(blue_balance)
                            print(f"Blue Balance in Kamera Einstellungen geändert:{cam.BalanceRatio.get()}")
                        except Exception as e:
                            log_schreiben(f"Fehler beim Setzen des Weißabgleichs bei der Bildaufnahme. Nutze default der Einstellungsdatei (XML): {e}", log_mode=log_mode)

                    if cam_mode == "display":
                        show_message("cam_5", lang=lang)
                        LepiLED_start("")
                        display_text_and_image("", "UV", "", "/home/Ento/LepmonOS/startsequenz/Warnung_UV.png", 2)

                    if cam_mode != "focus":
                        dim_up()
                        try:
                            _, _, _, power_vis, _ = get_power()
                        except Exception:
                            power_vis = "---"
                    try:
                        frame = cam.get_frame(timeout_ms=5000).as_opencv_image()
                        print("frame erfolgreich aufgenommen")
                        # --- Flatfield-Korrektur (greift nur bei gueltigem Flat
                        #     und passender Groesse; sonst unveraendertes Original) ---
                        if _FLAT is not None and frame is not None:
                            print("wende Flatfiled Korrektur an...")
                            if frame.shape[:2] == _FLAT.shape[:2]:
                                frame = apply_flatfield(frame, _FLAT)
                                print("Flatfield-Korrektur angewandt")
                            else:
                                log_schreiben(
                                    f"Flatfield-Groesse {_FLAT.shape[:2]} != Frame "
                                    f"{frame.shape[:2]} -> Korrektur uebersprungen.",
                                    log_mode=log_mode)


                    except Exception as e:
                        log_schreiben(f"Fehler bei der Frame Aufnahme:{e}", log_mode=log_mode)

                    if cam_mode != "focus":
                        dim_down()
                    
                    if cam_mode == "display":
                        show_message("cam_6", lang=lang)
                        LepiLED_ende("show")

                    Kamera_Status = 1
                    if cam_mode == "display":
                        show_message("cam_2", lang=lang)

    except Exception as e:
            frame = None
            Kamera_Status = 0
            cams = None
            if cam_Initiliase_tries > 2:
                show_message("err_1a", lang=lang, tries=cam_Initiliase_tries)
                print(f"Fehler beim Abrufen des Frames: {e}")
                print(f"Prüfe Kamera Verbindung und Stromversorgung. Versuch {cam_Initiliase_tries}")
                error_details = str(e)



    return frame, Kamera_Status, power_vis


def snap_image_AV(file_extension, cam_mode, Kamera_Fehlerserie, log_mode, Exposure, Gain=9, sn=""):
    """
    Args:
        file_extension (str): Dateierweiterung des Bildes.
        cam_mode (str): Betriebsmodus der Kamera.
            - "display": Lokale Anzeige während des HMI
            - "log": Speichern in der Schleife
            - "kamera_test": Test der Kamera (Einzelbild) oder des Skriptes
            - "Diagnose": Diagnoseskript in Geräteeinrichtung
    """
    code = 000
    power_on = 0
    image_file = ""
    Bild_erfolgreich_gespeichert = False
    HARDWARE_VERSION = get_hardware_version()

    avg_brightness, good_exposure = "---", False

    camera.on()

    if cam_mode == "display": 
        log_schreiben("Kamera wird eingeschaltet und initialisiert...", log_mode=log_mode)
        show_message("cam_4", lang=lang)

    ordnerpfad = get_value_from_section(
        "/home/Ento/LepmonOS/Lepmon_config.json", "general", "current_folder"
    )

    if cam_mode != "kamera_test":
        project_name, province, Kreis_code, sensor_id = get_Lepmon_code(log_mode)
        now = datetime.now() 
        if now.strftime('%Y') < '2026':
            now = Zeit_überschrieben(now, log_mode="log")

        if Enable_Interval:
            time_format = "%H%M%S"
        else:
            time_format = "%H%M"

        code = (
            f"{project_name}{sensor_id}_{province}_{Kreis_code}_"
            f"{now.strftime('%Y-%m-%d')}_T_{now.strftime(time_format)}"
        )

        image_file = f"{code}.{file_extension}"
        dateipfad = os.path.join(ordnerpfad, image_file)
    
    if cam_mode == "kamera_test":
        if not os.path.exists(ordnerpfad):
            ordnerpfad = erstelle_ordner("kamera_test", "AV__Alvium_1800_U-2050")
            print(f"Ordner '{ordnerpfad}' wurde erstellt.")
        log_dateipfad = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "general", "current_log")
        print(f"gelesener Logdateipfad: {log_dateipfad}")
        if not os.path.exists(log_dateipfad):
            print(f"Logdatei existiert nicht, erstelle neue Logdatei\nfalls ein Problem mit der Echteituhr oder dem I2C Bus besteht, das Argument 'ignore_time' auf True setzen, um die Logdatei zu erstellen.")
            log_dateipfad= initialisiere_logfile(log_mode, ignore_time = False)
            write_value_to_section("/home/Ento/LepmonOS/Lepmon_config.json", "general", "current_log", log_dateipfad)
            print(f"Logdatei innerhalb der Camera_AV Funktion neu estellt: {log_dateipfad}")

        image_file = f"AV__Alvium_1800_U-2050_{Exposure}_{Gain}__{round(ContrastShape,1)}.jpg"
        dateipfad = os.path.join(ordnerpfad, image_file)
        print(f"Kamera Test Bild wird gespeichert in: {dateipfad}")
        #time.sleep(2)

    if cam_mode == "Diagnose":
        image_file = f"{ordnerpfad}/Lepmon_Diagnose_{sn}_Testbild.jpg"
        dateipfad = image_file
        print(f"Kamera Diagnose Bild wird gespeichert in: {dateipfad}")

    #if cam_mode != "Diagnose":
    #    time.sleep(4)

    if cam_mode == "display":
        ordnerpfad, _ = get_usb_path(log_mode)
        dateipfad = os.path.join(ordnerpfad, "Testbild.jpg")
        log_schreiben(f"Dateipfad für Testbild: {dateipfad}", log_mode=log_mode)

    #if cam_mode == "log":
    #    time.sleep(5)


    # prüfen ob Ordnerpfad existiert, außer im display Modus, da hier nur ein Testbild gespeichert wird und der Ordner nicht zwingend vorhanden sein muss

    if not os.path.exists(ordnerpfad) and cam_mode != "display":
        if ordnerpfad == "":
            ordnerpfad = erstelle_ordner(log_mode, Cameramodel = "None")
            write_value_to_section("/home/Ento/LepmonOS/Lepmon_config.json", "general", "current_folder", ordnerpfad)
            print(f"Ordnerpfad war leer, neuer Ordner erstellt: {ordnerpfad}")
            print("Skript neu starten, um mit dem neuen Ordner zu arbeiten.")
        error_message(3, f"USB-Stick nicht gefunden: {ordnerpfad}", log_mode)
        print(f"Fehler: USB-Stick nicht gefunden: {ordnerpfad}")
        Status_Kamera = 0
       
        return code, dateipfad, Status_Kamera, power_on, Kamera_Fehlerserie, avg_brightness, good_exposure, Exposure, Gain
    
    
    # Abrufen des Frames in Abhängigkeit vom Kameramodus

    if cam_mode == "display":
        log_schreiben("Versuche Frame von Kamera abzurufen...", log_mode=log_mode)
        frame, Status_Kamera, power_vis = get_frame_AV(Exposure, cam_mode, log_mode, Gain, gamma)
        if frame is None:
            error_message(1, "Fehler beim Abrufen des Frames", log_mode)
        elif frame is not None:
            log_schreiben("Frame erfolgreich von Kamera abgerufen", log_mode=log_mode)
            try:
                cv2.imwrite(dateipfad, frame)
                log_schreiben(f"Testbild erfolgreich gespeichert:{dateipfad}", log_mode=log_mode)
                show_message("cam_7", lang=lang)
                os.remove(dateipfad)
                log_schreiben(f"Testbild vom Speicher gelöscht: {dateipfad}", log_mode=log_mode)
                log_schreiben("Kamera Zugriff erfolgreich", log_mode=log_mode)
            except Exception as e:
                print(f"Kamerafehler:{e}")
                error_message(3, f"Bild konnte nicht gespeichert werden: {dateipfad}", log_mode)
                log_schreiben(f"Fehlerdetails: {e}", log_mode=log_mode)
                Status_Kamera = 0


    
    if cam_mode == "Diagnose" or cam_mode == "kamera_test":
        frame, Status_Kamera, power_vis = get_frame_AV(Exposure, cam_mode, log_mode, Gain, gamma)
        time.sleep(0.5)
        try:
            cv2.imwrite(dateipfad, frame)
            print(f"Bild erfolgreich gespeichert!\nPfad: {dateipfad}")
            Status_Kamera = 1
            log_schreiben(f"Bild gespeichert: {dateipfad}", log_mode=log_mode)

        except Exception as e:
                print(f"Kamerafehler:{e}")
                log_schreiben(f"Fehler beim Speichern des Bildes: {dateipfad}", log_mode=log_mode)  
                Status_Kamera = 0
        try:
            _, _, _, power_cam, _ = get_power()
            if HARDWARE_VERSION in ["Pro_Gen_1", "Pro_Gen_2"]:
                print("Stromverbrauch der Visible LED kann auf diesem ARNI-Modell nicht gemessen werden.")
                power_on = "---"
            elif HARDWARE_VERSION in ["Pro_Gen_3", "Pro_Gen_4", "CSL_Gen_1", "CSS_Gen_1"]:
                power_on = round(power_vis - power_cam, 2)
            time.sleep(0.1)
        except Exception as e:
            power_on = "---"
            log_schreiben(f"Fehler beim Messen des Stromverbrauchs der Visible LED: {e}. Power_Vis:{power_vis}, Power_cam:{power_cam}", log_mode=log_mode)
        try: 
            Bild_erfolgreich_gespeichert = check_image(dateipfad, log_mode = "log")
        except Exception as e:
            log_schreiben(f"Fehler bei der Bildprüfung: {e}", log_mode=log_mode)
        if Bild_erfolgreich_gespeichert:
            print("Foto Sanity Check bestanden")
            Kamera_Fehlerserie = 0
        elif not Bild_erfolgreich_gespeichert:
            print("Foto Sanity nicht Check bestanden")
            Kamera_Fehlerserie += 1



    
    if cam_mode == "log":
        _, now, _ = Zeit_aktualisieren(log_mode=log_mode)
        sanity_tries = 0

        while (not Bild_erfolgreich_gespeichert) and (sanity_tries < 3):
            print(f"Versuch {sanity_tries + 1}: Bildaufnahme und Speicherung läuft...")
           
            now_dt = datetime.strptime(now, "%H:%M:%S")
            write_timestamp(0x07E0)
            show_message("blank", lang=lang)
            frame, Status_Kamera, power_vis = get_frame_AV(Exposure, cam_mode, log_mode, Gain, gamma, ContrastShape)

            if frame is not None:
                try:
                    cv2.imwrite(dateipfad, frame)
                    print(f"Bild erfolgreich gespeichert!\nPfad: {dateipfad}")
                    Status_Kamera = 1
                    log_schreiben(f"Bild gespeichert: {dateipfad}", log_mode=log_mode)

                except Exception as e:
                    print(f"Kamerafehler:{e}")
                    error_message(3, f"Bild konnte nicht gespeichert werden: {dateipfad}", log_mode)
                    Status_Kamera = 0
                    Kamera_Fehlerserie += 1
                    raise RuntimeError(f"Bild konnte nicht gespeichert werden: {e}")

                if Skip_Sanity_Check:
                    Bild_erfolgreich_gespeichert = True
                    Kamera_Fehlerserie = 0
                elif not Skip_Sanity_Check:
                    time.sleep(0.5)
                    try: 
                        Bild_erfolgreich_gespeichert = check_image(dateipfad, log_mode = "log")
                    except Exception as e:
                        log_schreiben(f"Fehler bei der Bildprüfung: {e}", log_mode=log_mode)

                    if Bild_erfolgreich_gespeichert:
                        print("Foto Sanity Check bestanden")
                        Kamera_Fehlerserie = 0
                        break
                    elif not Bild_erfolgreich_gespeichert:
                        sanity_tries += 1
                        log_schreiben(f"Foto Sanity Check im letzten Versuch Nr {sanity_tries} nicht bestanden, versuche erneut. Versuch {sanity_tries + 1}", log_mode=log_mode)



            elif frame is None:
                sanity_tries += 1
                log_schreiben("Kein Frame zum Speichern vorhanden", log_mode)
        avg_brightness, Exposure, Gain, good_exposure = calculate_Exposure_and_gain(
                frame, Exposure, Gain, "AV__Alvium_1800_U-2050", log_mode
                )
        avg_brightness = round(avg_brightness, 0)

        if sanity_tries>=3:
            Kamera_Fehlerserie += 1
            log_schreiben(f"Foto hat Sanity Check nach {sanity_tries} Versuchen endgültig nicht bestanden.", log_mode=log_mode)
            log_schreiben(f"erhöhe Kamera Fehlerserie auf {Kamera_Fehlerserie}", log_mode=log_mode)

    print(f"Status Kamera: {Status_Kamera}, Fehlerserie: {Kamera_Fehlerserie}, Foto OK: {Bild_erfolgreich_gespeichert}")
    camera.off()
    #camera.close()

    if HARDWARE_VERSION in ["Pro_Gen_1", "Pro_Gen_2"]:
            print("Stromverbrauch der Visible LED kann auf diesem ARNI-Modell nicht gemessen werden.")
    elif HARDWARE_VERSION in ["Pro_Gen_3", "Pro_Gen_4", "CSL_Gen_1", "CSS_Gen_1"]:
        try:
            _, _, _, power_cam, _ = get_power()
            power_on = round(power_vis - power_cam, 2)
            time.sleep(0.1)
        except Exception as e:
            log_schreiben(f"Fehler beim Messen des Stromverbrauchs der Visible LED: {e}. Power_Vis:{power_vis} W, Power_cam:{power_cam} W", log_mode=log_mode)

    return code, dateipfad, Status_Kamera, power_on, Kamera_Fehlerserie, avg_brightness, good_exposure, Exposure, Gain




if __name__ == "__main__":
    print("Nehme ein Bild mit der AV Kamera auf")
    exposure = int(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "AV__Alvium_1800_U-2050", "initial_exposure"))
    gain =     int(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "AV__Alvium_1800_U-2050", "initial_gain_10")) / 10
    snap_image_AV("jpg", "kamera_test", 0, "manual", exposure, gain)


'''    if os.environ.get("FORCE_LOAD_SETTINGS_ERROR") == "1":
        from unittest.mock import patch
        from vmbpy import Camera as _Camera
        print("ACHTUNG: FORCE_LOAD_SETTINGS_ERROR aktiv - erzwinge Fehler beim Laden der Kameraeinstellungen")
        with patch.object(_Camera, "load_settings", side_effect=RuntimeError("RetriesExceeded (simuliert)")):
            snap_image_AV("jpg", "kamera_test", 0, "manual", exposure, gain)
    else:
        snap_image_AV("jpg", "kamera_test", 0, "manual", exposure, gain)
'''