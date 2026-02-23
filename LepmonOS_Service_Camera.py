#########################
#########################
# This file is obsolete #
#########################
#########################

from GPIO_Setup import *
from OLED_panel import display_text
from Lights import *
import time
from gpiozero import LED


status_camera = 0
status_visible = 0
status_uv = 0


camera = LED(5)

display_text("oben   = UV",
             "Rechts = Cam",
             "unten  = Visible",0)

while True:
    
    if button_pressed("unten") and status_visible == 0:
        status_visible = 1
        dim_up()
        print("visible on")
    if button_pressed("unten") and status_visible == 1:
        status_visible = 0
        dim_down()
        print("visible off")
    
    if button_pressed("oben") and status_uv == 0:
        status_uv = 1
        LepiLED_start()
        print("UV on")
    if button_pressed("oben") and status_uv == 1:
        status_uv = 0
        LepiLED_ende()
        print("UV off")
    
    if button_pressed("rechts") and status_camera == 0:
        status_camera = 1
        camera.on()
        print("camera on")
    if button_pressed("rechts") and status_camera == 1:
        status_camera = 0
        camera.off()
        print("camera off")
        
    time.sleep(0.1)