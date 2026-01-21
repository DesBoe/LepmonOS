# SPDX-FileCopyrightText: 2021 ladyada for Adafruit Industries
# SPDX-License-Identifier: MIT

import time
from datetime import datetime, timedelta
import board
import adafruit_ds3231
from logging_utils import error_message
from times import *





def set_alarm(power_on, power_off, log_mode):
    
    """
    Setzt den Alarm auf die RTC
    :param alaram: 1 oder 2
    :param timestring: String im Format "YYYY-MM-DD HH:MM:SS"
    """
    i2c = board.I2C()
    try:
        rtc = adafruit_ds3231.DS3231(i2c)
        alarm1_time = time.strptime(power_on, "%Y-%m-%d %H:%M:%S")
        rtc.alarm1 = (alarm1_time, "daily")
        rtc.alarm1_status = False
        rtc.alarm1_interrupt = True
        #print("Alarm 1 gesetzt auf:", time.strftime("%Y-%m-%d %H:%M:%S", alarm1_time))

        alarm2_time = time.strptime(power_off, "%Y-%m-%d %H:%M:%S")
        rtc.alarm2 = (alarm2_time, "daily")
        rtc.alarm2_interrupt = True
        #print("Alarm 2 gesetzt auf:", time.strftime("%Y-%m-%d %H:%M:%S", alarm2_time))
    
    except Exception as e:
        error_message(8, e, log_mode)


if __name__ == "__main__":
    rtc = adafruit_ds3231.DS3231(board.I2C())
    now_str, _ ,_= Zeit_aktualisieren(log_mode="manual")  
    now = datetime.strptime(now_str, "%Y-%m-%d %H:%M:%S")  
    print( "Aktuelle Zeit:  ", now_str)

    now_plus_one_minute = (now + timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M:%S")
    now_plus_one_day = (now + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
    print("Zeit des Alarms:", now_plus_one_minute)

    set_alarm(now_plus_one_minute, now_plus_one_day, log_mode="manual")
    print("Zähle bis zum Alarm... der Alarm wird bei 60 erwartet")
    i = 1
    while True:
        print(i)
        i += 1
        time.sleep(1)
        
        if rtc.alarm1_status:
            print("Alarm 1 ausgelöst!")
            rtc.alarm1_status = False
            print("Ende des Alarm Tests")
            break
        