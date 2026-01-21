import os
os.environ["QT_QPA_PLATFORM"] = "xcb"
from picamera2 import Picamera2, Preview
import time

def check_connected_camera():
    print("suche nach angeschlossener RPi Kamera...")
    camera_tries = 0
    picam2 = None
    
    while picam2 == None and camera_tries < 90:
        try:   
            picam2 = Picamera2() 
            
        except Exception as e:
            print(f"Fehler beim Initialisieren der Kamera: {e}")
            print(f"Versuche im Terminal 'libcamera-hello' auszuführen, um die Kamera zu testen. Versuch {camera_tries}")
            picam2 = None
            camera_tries += 1
        time.sleep(.1)
    
    if picam2 is not None:
        print("Kamera gefunden. Lese Eigenschaften aus...")
        properties = picam2.camera_properties
        picam2.stop()
        picam2.close() 

        print(f"{'Property':<30} {'Value':<50}")
        print("-" * 80)
        for key, value in properties.items():
            print(f"{key:<30} {str(value):<50}")
            
        # Sensortyp und maximale Auflösung auslesen
        sensor_type = properties.get("Model", "Unbekannt")
        max_resolution = properties.get("PixelArraySize", (0, 0))
        print(f"Sensortyp: {sensor_type}")
        print(f"Maximale Auflösung: {max_resolution[0]} x {max_resolution[1]}")

        return sensor_type, max_resolution[0], max_resolution[1]

    return None, 0, 0

if __name__ == "__main__":
    sensor, length, height = check_connected_camera()
    print(f" erkannter Sensor: {sensor} mit Auflösung {length} x {height}")
    