
from times import *
from service import get_disk_space
from json_read_write import get_value_from_section, get_coordinates


def get_web_table_object(log_mode="web_stream"):
    """
    Erstellt ein vollständiges Objekt mit allen Zeitberechnungen,
    Standortdaten (Lat/Lon/Provinz/Stadt) und USB-Stick-Info.
    Wird vom Web-Service für /api/timing und /api/location genutzt.
    """
    result = {}

    # ── Config-Pfad ──
    config_path = "/home/Ento/LepmonOS/Lepmon_config.json"

    # ── 1. Sun Times: sunset, sunrise ──
    sunset_str = "---"
    sunrise_str = "---"
    try:
        sunset, sunrise, zeitzone = get_sun(log_mode)
        sunset_str = sunset.strftime("%H:%M:%S")
        sunrise_str = sunrise.strftime("%H:%M:%S")
    except Exception as e:
        print(f"[times] Sonnenzeiten konnten nicht berechnet werden: {e}")

    result["sunset"] = sunset_str
    result["sunrise"] = sunrise_str

    # ── 2. Experiment Times: start/end capture ──
    start_capture = "---"
    end_capture = "---"
    try:
        exp_start, exp_end, _, _ = get_experiment_times(log_mode)
        start_capture = exp_start
        end_capture = exp_end
    except Exception as e:
        print(f"[times] Experimentzeiten konnten nicht berechnet werden: {e}")

    result["start_capture"] = start_capture
    result["end_capture"] = end_capture

    # ── 3. Power Times: attiny ON/OFF ──
    attiny_on = "---"
    attiny_off = "---"
    try:
        power_on, power_off = get_times_power(log_mode)
        attiny_on = power_on
        attiny_off = power_off
    except Exception as e:
        print(f"[times] Powerzeiten konnten nicht berechnet werden: {e}")

    result["attiny_on"] = attiny_on
    result["attiny_off"] = attiny_off

    # ── 4. Config Offsets ──
    try:
        result["minutes_after_sunset"] = get_value_from_section(
            config_path, "capture_mode", "minutes_after_sunset")
        result["minutes_to_sunrise"] = get_value_from_section(
            config_path, "capture_mode", "minutes_to_sunrise")
        result["timebuffer_powermanager"] = get_value_from_section(
            config_path, "capture_mode", "timebuffer_powermanager")
    except Exception:
        result["minutes_after_sunset"] = "---"
        result["minutes_to_sunrise"] = "---"
        result["timebuffer_powermanager"] = "---"



    # ── 5. Coordinates (lat/lon) ──
    try:
        latitude, longitude, pol, block, lat_abs, lon_abs = get_coordinates()
        result["latitude"] = latitude
        result["longitude"] = longitude
        result["pol"] = pol
        result["block"] = block
        result["latitude_abs"] = lat_abs
        result["longitude_abs"] = lon_abs
    except Exception as e:
        print(f"[times] Koordinaten konnten nicht gelesen werden: {e}")
        result["latitude"] = 0.0
        result["longitude"] = 0.0
        result["pol"] = ""
        result["block"] = ""
        result["latitude_abs"] = 0.0
        result["longitude_abs"] = 0.0

    # ── 6. Locality: Province, City (Kreis) ──
    try:
        result["province"] = get_value_from_section(
            config_path, "locality", "province")
        result["city"] = get_value_from_section(
            config_path, "locality", "Kreis")
        result["country"] = get_value_from_section(
            config_path, "locality", "country")
    except Exception:
        result["province"] = "---"
        result["city"] = "---"
        result["country"] = "---"

    # ── 7. USB Stick Info ──
    result["usb_mounted"] = False
    result["usb_path"] = None
    result["usb_total_gb"] = 0
    result["usb_used_gb"] = 0
    result["usb_available_gb"] = 0
    result["usb_used_percent"] = 0
    result["usb_available_percent"] = 0
    try:
        total_space_gb, used_space_gb, free_space_gb, used_percent, free_percent = get_disk_space(log_mode)
        result["usb_mounted"] = True
        result["usb_path"] = get_value_from_section(config_path, "general", "usb_drive")
        result["usb_total_gb"] = total_space_gb
        result["usb_used_gb"] = used_space_gb
        result["usb_available_gb"] = free_space_gb
        result["usb_used_percent"] = round(used_percent, 1)
        result["usb_available_percent"] = round(free_percent, 1)

    except Exception as e:
        print(f"[times] USB-Info konnte nicht gelesen werden: {e}")
        result["usb_mounted"] = False
        result["usb_path"] = None
        result["usb_total_gb"] = 0
        result["usb_used_gb"] = 0
        result["usb_available_gb"] = 0
        result["usb_used_percent"] = 0
        result["usb_available_percent"] = 0

    #---8. Current Step---
    try:
        result["current_step"] = get_value_from_section(config_path, "general", "current_step")
    except Exception:
        result["current_step"] = "---"

    return result

if __name__ == "__main__":
    import json
    web_table = get_web_table_object(log_mode="manual")
    print(json.dumps(web_table, indent=2, default=str))
    # Clean up I2C bus to avoid segmentation fault on exit
    try:
        from fram_direct import bus
        if bus is not None:
            bus.close()
    except Exception:
        pass