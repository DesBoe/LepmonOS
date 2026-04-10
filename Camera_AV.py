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
from hardware import get_hardware_version

lang = get_language()


def get_frame(Exposure, cam_mode, log_mode, Gain):
    error_details = ""
    cams = None
    cam_Initiliase_tries = 0
    power_vis = "---"
    frame = None
    Kamera_Status = 0

    while cams is None:
        if cam_mode == "display" and cam_Initiliase_tries == 0:
            show_message("cam_1", lang=lang)

        cam_Initiliase_tries += 1
        time.sleep(0.1)

        try:
            with VmbSystem.get_instance() as vmb:
                cams = vmb.get_all_cameras()
                if not cams:
                    raise RuntimeError("Keine Kamera gefunden (vmbpy).")

                with cams[0] as cam:
                    try:
                        cam.set_pixel_format(PixelFormat.Bgr8)
                    except Exception as e:
                        print(f"Could not set pixel format: {e}")

                    settings_file = "/home/Ento/LepmonOS/Kamera_Einstellungen.xml".format(cam.get_id())
                    try:
                        cam.load_settings(settings_file, PersistType.All)
                    except Exception as e:
                        print(f"Could not load settings: {e}")

                    cam.ExposureTime.set(Exposure * 1000)
                    print(f"Exposure in Kamera Einstellungen geändert:{(cam.ExposureTime.get()/1000):.0f}")

                    cam.Gain.set(Gain)
                    print(f"Gain in Kamera Einstellungen geändert:{cam.Gain.get()}")

                    if cam_mode != "focus" and cam_mode != "Sensor_Suche":
                        dim_up()
                        try:
                            _, _, _, power_vis, _ = get_power()
                        except Exception:
                            power_vis = "---"

                    frame = cam.get_frame(timeout_ms=5000).as_opencv_image()

                    if cam_mode != "focus" and cam_mode != "Sensor_Suche":
                        dim_down()

                    Kamera_Status = 1
                    if cam_mode == "display":
                        show_message("cam_2", lang=lang)
                        print("frame erfolgreich aufgenommen")

        except Exception as e:
            frame = None
            Kamera_Status = 0
            cams = None
            if cam_Initiliase_tries > 5:
                show_message("err_1a", lang=lang, tries=cam_Initiliase_tries)
                print(f"Fehler beim Abrufen des Frames: {e}")
                print(f"Prüfe Kamera Verbindung und Stromversorgung. Versuch {cam_Initiliase_tries}")

        if cam_Initiliase_tries > 5:
            print(f"Kamera nach {cam_Initiliase_tries} Versuchen nicht initalisiert")
            log_schreiben(f"Kamera nach {cam_Initiliase_tries} Versuchen nicht initalisiert", log_mode=log_mode)
            show_message("cam_3", lang=lang)
            time.sleep(5)
            if not error_details:
                error_details = f"Kamera nach {cam_Initiliase_tries} Versuchen nicht initalisiert"
            error_message(1, error_details, log_mode)
            log_schreiben(f"Fehlerdetails: {error_details}", log_mode=log_mode)
            print(f"Fehler beim Abrufen des Frames: {e}")
            print("Prüfe Kamera Verbindung und Stromversorgung")
            break

    return frame, Kamera_Status, power_vis


def snap_image(file_extension, cam_mode, Kamera_Fehlerserie, log_mode, Exposure, Gain=9):
    """
    nimmt ein Bild auf

    :param file_extension: Dateierweiterung
    :param cam_mode: "display" für lokale ausgabe; "log" für speichern in der schleife;
                     "kamera_test" für Kameratest, "Sensor_Suche" für Sensormodell Abfrage
    """
    sensor = "imx183"
    length = 5496
    height = 3672
    code = 000
    power_on = 0
    image_file = ""

    avg_brightness, good_exposure = "---", False
    image_correction = get_value_from_section(
        "/home/Ento/LepmonOS/Lepmon_config.json", "image_quality", "gamma_correction"
    )
    gamma = get_value_from_section(
        "/home/Ento/LepmonOS/Lepmon_config.json", "image_quality", "gamma_value"
    )

    camera = LED(5)
    camera.on()

    if cam_mode != "kamera_test":
        project_name, province, Kreis_code, sensor_id = get_Lepmon_code(log_mode)
        ordnerpfad = get_value_from_section(
            "/home/Ento/LepmonOS/Lepmon_config.json", "general", "current_folder"
        )
        now = datetime.now()
        code = (
            f"{project_name}{sensor_id}_{province}_{Kreis_code}_"
            f"{now.strftime('%Y')}-{now.strftime('%m')}-{now.strftime('%d')}_T_{now.strftime('%H%M')}"
        )
        image_file = f"{code}.{file_extension}"
        dateipfad = os.path.join(ordnerpfad, image_file)

    if cam_mode == "kamera_test":
        ordnerpfad = get_value_from_section(
            "/home/Ento/LepmonOS/Lepmon_config.json", "general", "current_folder"
        )
        if not os.path.exists(ordnerpfad):
            erstelle_ordner(log_mode, Cameramodel="imx183")
            print(f"Ordner '{ordnerpfad}' wurde erstellt.")

        image_file = f"{sensor}_{Exposure}_{Gain}.jpg"
        dateipfad = os.path.join(ordnerpfad, image_file)
        print(f"Kamera Test Bild wird gespeichert in: {dateipfad}")

    time.sleep(4)

    if cam_mode == "display":
        show_message("cam_4", lang=lang)
        show_message("cam_5", lang=lang)
        display_text_and_image("", "UV", "", "/home/Ento/LepmonOS/startsequenz/Warnung_UV.png", 2)
        LepiLED_start()
        ordnerpfad, _ = get_usb_path(log_mode)
        dateipfad = os.path.join(ordnerpfad, image_file)
        print(f"Ordnerpfad für Testbild:{dateipfad}")

    if cam_mode == "log":
        time.sleep(5)

    frame, Status_Kamera, power_vis = get_frame(Exposure, cam_mode, log_mode, Gain)

    if cam_mode == "Sensor_Suche" and frame is not None and Status_Kamera == 1:
        print("Sensorsuche beendet")
        return sensor
    if cam_mode == "Sensor_Suche" and frame is None and Status_Kamera == 0:
        print("Keine AV Kamera erkannt.")
        return False

    if frame is not None:
        Kamera_Fehlerserie = 0
        if cam_mode == "log":
            avg_brightness, Exposure, Gain, good_exposure = calculate_Exposure_and_gain(
                frame, Exposure, Gain, log_mode
            )
            avg_brightness = round(avg_brightness, 0)

            if image_correction:
                time.sleep(1)
                print(f"Belichtungsoptimierung: Wende Gamma Korrektur an (gamma={gamma})", flush=True)
                if gamma is None:
                    print("FEHLER: gamma ist None!", flush=True)
                    raise ValueError("gamma darf nicht None sein!")
                if gamma == 0:
                    print("FEHLER: gamma ist 0!", flush=True)
                    raise ValueError("gamma darf nicht 0 sein!")

                height = frame.shape[0]
                split1 = height // 3
                split2 = 2 * height // 3

                teile = [frame[:split1], frame[split1:split2], frame[split2:]]
                del frame

                bearbeitet = []
                for i, teil in enumerate(teile):
                    print(f"korrigiere frame Teil {i+1}", flush=True)
                    teil = teil / 255.0
                    teil = np.power(teil, 1 / gamma)
                    teil = (teil * 255).astype(np.uint8)
                    bearbeitet.append(teil)
                    del teil
                    gc.collect()

                frame = np.vstack(bearbeitet)
                del bearbeitet
                gc.collect()
                print("Belichtungsoptimierung: Gamma Korrektur vollständig angewendet", flush=True)

    if frame is None:
        if cam_mode == "display":
            error_message(1, "Fehler beim Abrufen des Frames", log_mode)
        if cam_mode == "log":
            Kamera_Fehlerserie += 1

    if cam_mode == "log":
        time.sleep(0.5)
        try:
            _, _, _, power_cam, _ = get_power()
            power_on = round(power_vis - power_cam, 2)
            time.sleep(0.1)
        except Exception as e:
            power_on = "---"
            print(f"Fehler beim Messen des Stromverbrauchs der Visible LED: {e}")

    camera.off()
    camera.close()

    if cam_mode == "display":
        show_message("cam_6", lang=lang)
        LepiLED_ende()

    if not os.path.exists(ordnerpfad) and cam_mode != "display":
        if ordnerpfad == "":
            ordnerpfad = "Ordnerpfad ist leer!"
        error_message(3, f"USB-Stick nicht gefunden: {ordnerpfad}", log_mode)
        print(f"Fehler: USB-Stick nicht gefunden: {ordnerpfad}")
        print("Zum erstellen des Ordners bitte USB-Stick anschließen und start_up.py ausführen ")
        return (
            code,
            dateipfad,
            Status_Kamera,
            power_on,
            Kamera_Fehlerserie,
            sensor,
            length,
            height,
            avg_brightness,
            good_exposure,
            Exposure,
            Gain,
        )

    if frame is not None:
        try:
            cv2.imwrite(dateipfad, frame)
            Status_Kamera = 1

            if cam_mode == "display":
                show_message("cam_7", lang=lang)
                os.remove(dateipfad)
                print(f"Bild vom Speicher gelöscht: {dateipfad}")
                log_schreiben("Kamera Zugriff erfolgreich", log_mode=log_mode)

            if cam_mode == "log":
                log_schreiben(f"Bild gespeichert: {dateipfad}", log_mode=log_mode)

        except Exception as e:
            print(f"Kamerafehler:{e}")
            error_message(3, f"Bild konnte nicht gespeichert werden: {dateipfad}", log_mode)
            Status_Kamera = 0
            Kamera_Fehlerserie += 1
            return (
                code,
                dateipfad,
                Status_Kamera,
                power_on,
                Kamera_Fehlerserie,
                sensor,
                length,
                height,
                avg_brightness,
                good_exposure,
                Exposure,
                Gain,
            )
    else:
        print("Kein Bild zum Speichern vorhanden")

    if cam_mode == "log":
        write_timestamp(0x07E0)

    return (
        code,
        dateipfad,
        Status_Kamera,
        power_on,
        Kamera_Fehlerserie,
        sensor,
        length,
        height,
        avg_brightness,
        good_exposure,
        Exposure,
        Gain,
    )



#######################################################################################################################
#######################################################################################################################
#######################################################################################################################
def get_frame_AV(Exposure, cam_mode, log_mode, Gain, gamma=1):
    cams = None
    cam_Initiliase_tries = 0
    power_vis = "---"
    frame = None
    Kamera_Status = 0
    error_details = ""

    while cams is None:
        if cam_mode == "display" and cam_Initiliase_tries == 0:
            show_message("cam_1", lang=lang)

        cam_Initiliase_tries += 1
        time.sleep(0.1)

        try:
            with VmbSystem.get_instance() as vmb:
                cams = vmb.get_all_cameras()
                if not cams:
                    raise RuntimeError("Keine Kamera gefunden (vmbpy).")

                with cams[0] as cam:
                    print(f"Verwende gefundene Kamera:{cam}")
                    settings_file = "/home/Ento/LepmonOS/Kamera_Einstellungen_VimbaX.xml".format(cam.get_id()) # VimbaX uses an other format compared to Vimba
                    # BGR8 is included in the new version of the setings file

                    try:
                        cam.load_settings(settings_file, PersistType.All)
                        print("Kameraeinstellungen erfolgreich geladen")
                        time.sleep(5)
                    except Exception as e:
                        log_schreiben(f"Fehler beim Laden der Kameraeinstellungen: {e}", log_mode=log_mode)
                    
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

        if cam_Initiliase_tries > 90:
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

    return frame, Kamera_Status, power_vis


def snap_image_AV(file_extension, cam_mode, Kamera_Fehlerserie, log_mode, Exposure, Gain=9, sn=""):
    """
    Args:
        file_extension (str): Dateierweiterung des Bildes.
        cam_mode (str): Betriebsmodus der Kamera.
            - "display": Lokale Anzeige
            - "log": Speichern in der Schleife
            - "kamera_test": Test der Kamera oder des Skriptes
            - "Diagnose": Diagnose (Geräteeinrichtung)
    """
    code = 000
    power_on = 0
    image_file = ""
    Bild_erfolgreich_gespeichert = False
    hardware = get_hardware_version()

    avg_brightness, good_exposure = "---", False
    image_correction = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "capture_mode", "gamma_correction")
    if image_correction:
        gamma = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "AV__Alvium_1800_U-2050", "gamma_value")
    else:
        gamma = 1

    camera = LED(5)
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
        code = (
            f"{project_name}{sensor_id}_{province}_{Kreis_code}_"
            f"{now.strftime('%Y')}-{now.strftime('%m')}-{now.strftime('%d')}_T_{now.strftime('%H%M')}"
        )
        image_file = f"{code}.{file_extension}"
        dateipfad = os.path.join(ordnerpfad, image_file)

    if cam_mode == "kamera_test":
        if not os.path.exists(ordnerpfad):
            erstelle_ordner(log_mode, "AV__Alvium_1800_U-2050")
            print(f"Ordner '{ordnerpfad}' wurde erstellt.")

        image_file = f"AV__Alvium_1800_U-2050_{Exposure}_{Gain}.jpg"
        dateipfad = os.path.join(ordnerpfad, image_file)
        print(f"Kamera Test Bild wird gespeichert in: {dateipfad}")

    if cam_mode == "Diagnose":
        image_file = f"{ordnerpfad}/Lepmon_Diagnose_{sn}_Testbild.jpg"
        dateipfad = image_file
        print(f"Kamera Test Bild wird gespeichert in: {dateipfad}")

    if cam_mode != "Diagnose":
        time.sleep(4)

    if cam_mode == "display":
        ordnerpfad, _ = get_usb_path(log_mode)
        dateipfad = os.path.join(ordnerpfad, "Testbild.jpg")
        log_schreiben(f"Dateipfad für Testbild: {dateipfad}", log_mode=log_mode)

    if cam_mode == "log":
        time.sleep(5)


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


    
    if cam_mode == "Diagnose":
        frame, Status_Kamera, power_vis = get_frame_AV(Exposure, cam_mode, log_mode, Gain, gamma)
        time.sleep(0.5)
        try:
            cv2.imwrite(dateipfad, frame)
            print(f"Bild erfolgreich gespeichert!\nPfad: {dateipfad}")
            Status_Kamera = 1
            Kamera_Fehlerserie = 0
            log_schreiben(f"Bild gespeichert: {dateipfad}", log_mode=log_mode)

        except Exception as e:
                print(f"Kamerafehler:{e}")
                log_schreiben(f"Bild gespeichert: {dateipfad}", log_mode=log_mode)  
                Status_Kamera = 0
                Kamera_Fehlerserie += 1
        try:
            _, _, _, power_cam, _ = get_power()
            if hardware in ["Pro_Gen_1", "Pro_Gen_2"]:
                print("Stromverbrauch der Visible LED kann auf diesem ARNI-Modell nicht gemessen werden.")
                power_on = "---"
            elif hardware in ["Pro_Gen_3", "Pro_Gen_4", "CSL_Gen_1", "CSS_Gen_1"]:
                power_on = round(power_vis - power_cam, 2)
            time.sleep(0.1)
        except Exception as e:
            power_on = "---"
            log_schreiben(f"Fehler beim Messen des Stromverbrauchs der Visible LED: {e}", log_mode=log_mode)

    
    if cam_mode == "log":
        _, now, _ = Zeit_aktualisieren(log_mode=log_mode)
        sanity_tries = 0

        while (not Bild_erfolgreich_gespeichert) and (sanity_tries < 3):
            print(f"Versuch {sanity_tries + 1}: Bildaufnahme und Speicherung läuft...")
           
            now_dt = datetime.strptime(now, "%H:%M:%S")
            write_timestamp(0x07E0)
            show_message("blank", lang=lang)
            frame, Status_Kamera, power_vis = get_frame_AV(Exposure, cam_mode, log_mode, Gain, gamma)

            if frame is not None:
                Kamera_Fehlerserie = 0
                try:
                    cv2.imwrite(dateipfad, frame)
                    print(f"Bild erfolgreich gespeichert!\nPfad: {dateipfad}")
                    Status_Kamera = 1
                    Kamera_Fehlerserie = 0
                    log_schreiben(f"Bild gespeichert: {dateipfad}", log_mode=log_mode)

                except Exception as e:
                    print(f"Kamerafehler:{e}")
                    error_message(3, f"Bild konnte nicht gespeichert werden: {dateipfad}", log_mode)
                    Status_Kamera = 0
                    Kamera_Fehlerserie += 1
            
                try: 
                    Bild_erfolgreich_gespeichert = check_image(dateipfad, log_mode = "log")
                    if Bild_erfolgreich_gespeichert:
                        print("Foto Sanity Check bestanden")
                        break
                    elif not Bild_erfolgreich_gespeichert:
                        sanity_tries += 1

                except Exception as e:
                    print(f"Fehler bei der Bildprüfung: {e}")
                    sanity_tries += 1
                    

            elif frame is None:
                Kamera_Fehlerserie += 1
                log_schreiben("Kein Frame zum Speichern vorhanden", log_mode)
        avg_brightness, Exposure, Gain, good_exposure = calculate_Exposure_and_gain(
                frame, Exposure, Gain, "AV__Alvium_1800_U-2050", log_mode
                )
        avg_brightness = round(avg_brightness, 0)

        time.sleep(0.5)

        if sanity_tries>=4:
            log_schreiben(f"Foto hat Sanity Check nach {sanity_tries} Versuchen endgültig nicht bestanden.", log_mode=log_mode)

    print(f"Status Kamera: {Status_Kamera}, Fehlerserie: {Kamera_Fehlerserie}, Foto OK: {Bild_erfolgreich_gespeichert}")
    camera.off()
    camera.close()

    if hardware in ["Pro_Gen_1", "Pro_Gen_2"]:
            print("Stromverbrauch der Visible LED kann auf diesem ARNI-Modell nicht gemessen werden.")
    elif hardware in ["Pro_Gen_3", "Pro_Gen_4", "CSL_Gen_1", "CSS_Gen_1"]:
        try:
            _, _, _, power_cam, _ = get_power()
            power_on = round(power_vis - power_cam, 2)
            time.sleep(0.1)
        except Exception as e:
            log_schreiben(f"Fehler beim Messen des Stromverbrauchs der Visible LED: {e}", log_mode=log_mode)

    return code, dateipfad, Status_Kamera, power_on, Kamera_Fehlerserie, avg_brightness, good_exposure, Exposure, Gain




if __name__ == "__main__":
    import sys

    which = (sys.argv[1] if len(sys.argv) > 1 else "av").lower()

    if which in ("imx", "imx183"):
        print("Nehme ein Bild mit der IMX183 Kamera auf")
        gain, exposure = 9, 140
        snap_image("jpg", "display", 0, "log", float(exposure), float(gain))
    else:
        print("Nehme ein Bild mit der AV Kamera auf")
        exposure = int(
            get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "AV__Alvium_1800_U-2050", "initial_exposure")
        )
        gain = int(
            get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "AV__Alvium_1800_U-2050", "initial_gain_10")
        ) / 10
        snap_image_AV("jpg", "log", 0, "manual", exposure, gain)