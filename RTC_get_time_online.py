import socket
import requests
from datetime import datetime
import pytz

def is_wifi_connected():
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=2)
        return True
    except OSError:
        return False

def get_internet_time():
    if is_wifi_connected():
        response = requests.head("http://google.com", timeout=3)
        date_str = response.headers['Date']
        # Beispiel: 'Wed, 13 May 2026 12:50:00 GMT'
        dt_utc = datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %Z")
        # In deutsche Zeit (Europe/Berlin) umwandeln
        utc = pytz.timezone('UTC')
        berlin = pytz.timezone('Europe/Berlin')
        dt_utc = utc.localize(dt_utc)
        dt_berlin = dt_utc.astimezone(berlin)
        print(f'date_time_list aus dem Internet = "{dt_berlin}"')
        return dt_berlin.strftime("%Y%m%d%H%M%S")
    else:
        print("Kein WLAN verbunden, nutze default.")
        date_time_list = "20260416125000"
        return date_time_list

if __name__ == "__main__":
    date_time_list = get_internet_time()
    print(f'date_time_list = "{date_time_list}"')