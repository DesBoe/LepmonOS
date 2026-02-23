#########################
#########################
# This file is obsolete #
#########################
#########################

from Camera import snap_image
import time
import datetime


def wait_to_start():
    ### Startzeit###
    start = 22
    now = datetime.datetime.now()
    target_time = now.replace(hour=start, minute=0, second=0, microsecond=0)
    
    
    time_diff = target_time - now
    wait_seconds = time_diff.total_seconds()
    if wait_seconds > 0:
        time.sleep(wait_seconds)
    print("Starte Test der Belichtungszeiten und Gains")
    
if __name__ == "__main__":
    wait_to_start()
    for gain in range(2, 26):  # gain von 2 bis 25
        print(f"Starte Testreihe für Gain={gain}")
        for exposure in range(15, 211, 15):  # exposure von 15 bis 210 in 15er Schritten
            print(f"Exposure={exposure}ms")
            try:
                snap_image("jpg", "kamera_test", 0, exposure, gain=gain)
            except Exception as e:
                print(f"Fehler bei Gain={gain}, Exposure={exposure}: {e}")
            
            time.sleep(5)  # kurze Pause zwischen den Aufnahmen
                
