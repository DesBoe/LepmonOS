####
# Test für LED Driver
####

# Copy from Lights.py

from json_read_write import get_value_from_section
import RPi.GPIO as GPIO
import time
from hardware import get_hardware_version
from OLED_panel import *

LepiLed_pin = 26
Blitz_PMW = 350
HARDWARE_VERSION = get_hardware_version() 
if HARDWARE_VERSION == "Pro_Gen_1":
    dimmer_pin = 6
else:
    dimmer_pin = 13 

display_text("LED Driver Test", "", "")

GPIO.setmode(GPIO.BCM) # Initialisierung der GPIO und PWM außerhalb der Schleife
GPIO.setwarnings(False)
GPIO.setup(dimmer_pin, GPIO.OUT)
GPIO.setup(LepiLed_pin, GPIO.OUT)


dimmer_pwm = GPIO.PWM(dimmer_pin, Blitz_PMW)
LepiLed_pwm = GPIO.PWM(LepiLed_pin, Blitz_PMW)


def dim_up():
    flash = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","capture_mode","flash")

    dimmer_pwm.start(0)
    LepiLed_pwm.start(0)
    display_text("dimme hoch","","")
    for duty_cycle in range(0, 100,1):
        dimmer_pwm.ChangeDutyCycle(duty_cycle)
        LepiLed_pwm.ChangeDutyCycle(duty_cycle)
        time.sleep(flash / 100)
    dimmer_pwm.start(100)    
    LepiLed_pwm.ChangeDutyCycle(100)
    display_text("output high","","")
        #GPIO.output(dimmer_pin, GPIO.HIGH)
        
      
def dim_down(): 
    flash = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","capture_mode","flash") 

    dimmer_pwm.start(100)
    LepiLed_pwm.start(100)
    display_text("dimme runter","","")
    for duty_cycle in range(99, 0, -1):
        dimmer_pwm.ChangeDutyCycle(duty_cycle)
        LepiLed_pwm.ChangeDutyCycle(duty_cycle)
        time.sleep(flash / 100)
    dimmer_pwm.start(0)
    LepiLed_pwm.ChangeDutyCycle(0)
    display_text("output low","","")    
    #GPIO.output(dimmer_pin, GPIO.LOW)


    

if __name__ == "__main__":
    while True:
        dim_up()
        print("dimme hoch")
        time.sleep(1)
        dim_down()
        print("dimme runter")
        time.sleep(1)



########
########


####
# LepmonOS Diagnose für Kamerakabel und Wiederstand 
####
'''
from Camera_AV import *
from OLED_panel import *
from GPIO_Setup import *
from LepmonOS_Service_Diagnose import set_paths
from service import get_Lepmon_code

if __name__ == "__main__":
    step = 1
    display_text("Diagnose für", "Kamerakabel", "Wiederstand")
    log_mode = "manual"
    project_name,province, Kreis_code, sn = get_Lepmon_code(log_mode)
    set_paths(sn)
    time.sleep(2)
    while True:
        if step <= 1:
            for i in range(1,2):
                display_text("dimme hoch","","")
                turn_on_led("blau")
                dim_up()
                time.sleep(.5)
                display_text("dimme runter","","")
                dim_down()
                time.sleep(.5)
            step += 1

        if step <= 2:
            display_text("teste Kamera","","")

            for i in range(1,3):
                try:
                    snap_image_AV("jpg","Diagnose", 0, log_mode, 140,Gain = 7, sn = sn)
                    display_text("Bild aufgenommen","","")
                except:
                    display_text("Fehler - ","prüfe Kabel","und ggf Terminal")
            step += 1
            
            
            
            
            
            
            step = 1

        if step <= 3:
            for i in range(1,20):
                if button_pressed("oben"):
                    print("Oben gedrückt")
                    display_text("Oben gedrückt ","","")
                elif button_pressed("unten"):
                    print("Unten gedrückt")
                    display_text("Unten gedrückt ","","")
                elif button_pressed("rechts"):
                    print("Rechts gedrückt")
                    display_text("Rechts gedrückt ","","")
                elif button_pressed("enter"):
                    print("Enter gedrückt")
                    display_text("Enter gedrückt ","","")
                time.sleep(.05)
'''    
