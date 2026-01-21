from datetime import datetime, timedelta
from timezonefinder import TimezoneFinder
import pytz
import ephem
from logging_utils import error_message
from json_read_write import *
import board
import adafruit_ds3231



def Zeit_aktualisieren(log_mode):
    i2c = board.I2C()
    rtc_status = 0
    try:
        rtc = adafruit_ds3231.DS3231(i2c)
        rtc_status = 1
        t = rtc.datetime
        dt = datetime(t.tm_year, t.tm_mon, t.tm_mday, t.tm_hour, t.tm_min, t.tm_sec)
        jetzt_local = dt.strftime("%Y-%m-%d %H:%M:%S")
        lokale_Zeit = dt.strftime("%H:%M:%S")
    except Exception as e:
        error_message(8,e, log_mode)
        jetzt_local = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lokale_Zeit = datetime.now().strftime("%H:%M:%S")
    return jetzt_local, lokale_Zeit, rtc_status

def berechne_zeitzone(latitude,longitude):
    tf = TimezoneFinder()
    
    zeitzone_name = tf.timezone_at(lat=latitude, lng=longitude)
    
    if zeitzone_name is None:
        print("Keine Zeitzone gefunden für diese Koordinaten.")
        return None
    
    Zeitzone = pytz.timezone(zeitzone_name)

    return Zeitzone


def get_sun():
    latitude,longitude, _, _, _, _ = get_coordinates()
    day = datetime.utcnow()
    tf = TimezoneFinder()
    timezone_str = tf.timezone_at(lat=latitude, lng=longitude)
    tz = pytz.timezone(timezone_str) 
    
    obs = ephem.Observer()
    obs.lat = str(latitude)
    obs.lon = str(longitude)
    obs.date = day.strftime("%Y/%m/%d")  # UTC Datum 
    
    # Sonne berechnen
    sunrise_utc = obs.next_rising(ephem.Sun(), use_center=True).datetime()
    sunset_utc = obs.next_setting(ephem.Sun(), use_center=True).datetime()

    # In lokale Zeit umwandeln
    sunrise_local = pytz.utc.localize(sunrise_utc).astimezone(tz)
    sunset_local = pytz.utc.localize(sunset_utc).astimezone(tz)
    
    if sunrise_local.date() == sunset_local.date():
        sunrise_local = sunrise_local + timedelta(days=1)
    
    
    return sunset_local, sunrise_local, tz
    
    
def get_moon(log_mode):
    jetzt_local = datetime.now()
    try:
        latitude, longitude, _, _, _, _ = get_coordinates()
    except Exception as e:
        error_message(11, e, log_mode)
        return None, None, None, None

    Zeitzone = berechne_zeitzone(latitude, longitude)
    observer = ephem.Observer()
    observer.lat = str(latitude)
    observer.lon = str(longitude)

    # Lokale Zeit in UTC umwandeln
    jetzt_local_utc = jetzt_local.astimezone(pytz.utc)

    moonrise = ephem.localtime(observer.previous_rising(ephem.Moon(), start=jetzt_local_utc))
    moonset = ephem.localtime(observer.next_setting(ephem.Moon(), start=jetzt_local_utc))
    
    if moonrise and moonset and (moonset - moonrise).total_seconds() / 3600 > 13:
        moonset = ephem.localtime(observer.previous_setting(ephem.Moon(), start=jetzt_local_utc))
        moonrise = ephem.localtime(observer.next_rising(ephem.Moon(), start=jetzt_local_utc))
        print(f"Mond steht in dieser Nacht am Himmel und geht um {moonrise} auf und um {moonset} unter")
        

    moon = ephem.Moon(jetzt_local_utc)
    moon_phase = moon.phase  # Prozentuale Beleuchtung (0-100)

    next_transit = observer.next_transit(moon, start=jetzt_local_utc)
    observer.date = next_transit
    moon.compute(observer)
    max_altitude = moon.alt * 180.0 / ephem.pi  # in Grad

    return moonrise, moonset, moon_phase, max_altitude



def get_experiment_times():
    
    minutes_to_sunrise = timedelta(minutes=int(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "capture_mode", "minutes_to_sunrise")))
    minutes_to_sunset = timedelta(minutes=int(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "capture_mode", "minutes_to_sunset")))  
    
    sunset, sunrise, _ = get_sun()
    
    experiment_start_time = sunset - minutes_to_sunset
    experiment_end_time = sunrise - minutes_to_sunrise

    experiment_start_time = experiment_start_time.replace(tzinfo=None)
    experiment_start_time = experiment_start_time.strftime("%H:%M:%S")


    experiment_end_time = experiment_end_time.replace(tzinfo=None)
    experiment_end_time = experiment_end_time.strftime("%H:%M:%S")

    
    return experiment_start_time, experiment_end_time, minutes_to_sunset, minutes_to_sunrise


def get_times_power():
    minutes_to_sunset = timedelta(minutes=int(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "capture_mode", "minutes_to_sunset")))
    sunset, sunrise, _ = get_sun()
    
    power_on = sunset - minutes_to_sunset - timedelta(minutes=15)
    power_off = sunrise - timedelta(minutes=55)

    power_on = power_on.replace(tzinfo=None)
    power_on = power_on.strftime('%Y-%m-%d %H:%M:%S')

    power_off = power_off.replace(tzinfo=None)
    power_off = power_off.strftime('%Y-%m-%d %H:%M:%S')
    
    return power_on, power_off


def zeitumstellung_info(dt, zeitzone):
    """
    Gibt aus, ob an diesem Datum in der Zeitzone die Uhr vor- oder zurückgestellt wird.
    dt: datetime-Objekt (Datum, das geprüft werden soll)
    zeitzone: pytz.timezone-Objekt
    """
    # Zwei Zeitpunkte: vor und nach der typischen Umstellungszeit (2 Uhr)
    Zeit_Ändern, Änderung = False, 0
    #zeitzone = pytz.timezone(zeitzone)
    dt = datetime.strptime(dt, "%Y-%m-%d %H:%M:%S")
    dt_vor = zeitzone.localize(datetime(dt.year, dt.month, dt.day, 1, 59, 59), is_dst=None)
    dt_nach = zeitzone.localize(datetime(dt.year, dt.month, dt.day, 3, 0, 0), is_dst=None)
    offset_vor = dt_vor.utcoffset()
    offset_nach = dt_nach.utcoffset()
    if offset_vor != offset_nach:
        if offset_nach > offset_vor:
            print("Datum mit Zeitumstellung erkannt (Sommerzeit beginnt)")
            Zeit_Ändern, Änderung = True, -1
        else:
            print("Datum mit Zeitumstellung erkannt (Winterzeit beginnt)")
            Zeit_Ändern, Änderung = True, 1
    else:
        print("Keine Zeitumstellung an diesem Tag")
    return Zeit_Ändern, Änderung



if __name__ == "__main__":
    jetzt_local, lokale_Zeit, _ = Zeit_aktualisieren(log_mode="manual")
    print("Aktuelle Zeit:", jetzt_local)
    print("Aktuelle lokale Zeit:", lokale_Zeit)
    print("---------------------------------")
    sunset, sunrise, Zeitzone = get_sun()
    print(f"Sonnenuntergang: {sunset}")
    print(f"Sonnenaufgang: {sunrise}")
    print(f"Zeitzone: {Zeitzone}")
    latitude, longitude, _, _, _, _ = get_coordinates()
    print(f"Breitengrad:  {latitude}")
    print(f"Längengrad:   {longitude}")
    print("---------------------------------")
    moonrise, moonset, moon_phase, max_altitude = get_moon(log_mode="manual")
    print(f"Mondaufgang:   {moonrise}")
    print(f"Monduntergang: {moonset}")
    print(f"Mondphase:     {moon_phase:.1f}%")
    print(f"Maximale Kulminationshöhe: {max_altitude:.2f}°")
    print("---------------------------------")
    experiment_start_time, experiment_end_time, minutes_to_sunset, minutes_to_sunrise = get_experiment_times()
    print(f"Experiment Startzeit: {experiment_start_time}")
    print(f"Experiment Endzeit:   {experiment_end_time}")
    print(f"Puffer vor Sonnenuntergang: {minutes_to_sunset}")
    print(f"Puffer vor Sonnenaufgang:   {minutes_to_sunrise}")
    print("---------------------------------")
    power_on, power_off = get_times_power()
    print(f"Power On Zeit:  {power_on}")
    print(f"Power Off Zeit: {power_off}")
    print("---------------------------------")
    Zeitumstellung, Änderung = zeitumstellung_info(jetzt_local,Zeitzone)
    if Zeitumstellung:
        print(f"Zeitumstellung heute Tag, Änderung: {Änderung}")
    else:
        print("Keine Zeitumstellung an diesem Tag")
    print("---------------------------------")
    print("Teste mit Datum für Zeitumstellung:")
    dt_1 = "2025-10-26 15:55:45"
    print(dt_1)
    print("zum Testen der Zeitumstellung, auskommentieren")
    '''
    Zeitumstellung, Änderung = zeitumstellung_info(dt_1, Zeitzone)
    if Zeitumstellung:
        print(f"Zeitumstellung an diesem Tag, Änderung: {Änderung}")
    else:
        print("Keine Zeitumstellung an diesem Tag")
    '''
    print("---")