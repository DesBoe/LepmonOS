from GPIO_Setup import *
from OLED_panel import display_text
from Lights import *
import time
from gpiozero import LED


status_camera = 0
status_visible = 0
status_uv = 0
mode = "manual"


camera = LED(5)

zeile_1 = "oben   = UV"
zeile_2 = "Rechts = Cam"
zeile_3 = "unten  = Visible"

display_text(zeile_1, zeile_2, zeile_3, 0)


while True:
    display_text(zeile_1, zeile_2, zeile_3, 0)
    if button_pressed("unten") and status_visible == 0:
        status_visible = 1
        dim_up()
        print("visible on")
        zeile_3 = "unten  = Visible x"
        time.sleep(.2)
    if button_pressed("unten") and status_visible == 1:
        status_visible = 0
        dim_down()
        print("visible off")
        zeile_3 = "unten  = Visible"
        time.sleep(.2)
    
    if button_pressed("oben") and status_uv == 0:
        status_uv = 1
        LepiLED_start(mode)
        print("UV on")
        zeile_1 = "oben   = UV      x"
        
        time.sleep(.2)
    if button_pressed("oben") and status_uv == 1:
        status_uv = 0
        LepiLED_ende(mode)
        print("UV off")
        zeile_1 = "oben   = UV"
        
        time.sleep(.2)
    
    if button_pressed("rechts") and status_camera == 0:
        status_camera = 1
        camera.on()
        print("camera on")
        zeile_2 = "Rechts = Cam     x"
        time.sleep(.2)
    if button_pressed("rechts") and status_camera == 1:
        status_camera = 0
        camera.off()
        print("camera off")
        zeile_2 = "Rechts = Cam"
        time.sleep(.2)
    time.sleep(0.1)