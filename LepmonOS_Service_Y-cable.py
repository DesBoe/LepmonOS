#########################
#########################
# This file is obsolete #
#########################
#########################

from GPIO_Setup import *
from OLED_panel import display_text
from Lights import dim_up,dim_down
import time
from Camera import *


Status_Kamera = 0
dateipfad = None
Camera_versuche = 0


while True:
    if Camera_versuche <91:
        try:
            _, dateipfad, Status_Kamera, _, _ =  snap_image("jpg","cable",0,100)
            Camera_versuche = 0
        except Exception as e:
            Camera_versuche += 1
            print(e)
    elif Camer_versuche >91:
        print("Prüfe Kabel")
    display_text("","","unten = aus",0)
    if button_pressed("unten"):

        display_text("","","",0)
        break
    time.sleep(0.1)