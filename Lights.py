from json_read_write import get_value_from_section
import RPi.GPIO as GPIO
import time
from hardware import get_hardware_version
from OLED_panel import *

LepiLed_pin = 26
Blitz_PMW = 350
hardware = get_hardware_version() 
if hardware == "Pro_Gen_1":
    dimmer_pin = 6
else:
    dimmer_pin = 13 

GPIO.setmode(GPIO.BCM) # Initialisierung der GPIO und PWM außerhalb der Schleife
GPIO.setwarnings(False)
GPIO.setup(dimmer_pin, GPIO.OUT)
GPIO.setup(LepiLed_pin, GPIO.OUT)


dimmer_pwm = GPIO.PWM(dimmer_pin, Blitz_PMW)
LepiLed_pwm = GPIO.PWM(LepiLed_pin, Blitz_PMW)


def dim_up():
    
    flash = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","capture_mode","flash")
    dimmer_pwm.start(0)
    for duty_cycle in range(0, 99,1):
        dimmer_pwm.ChangeDutyCycle(duty_cycle)
        time.sleep(flash / 100)
    dimmer_pwm.start(100)    
    #GPIO.output(dimmer_pin, GPIO.HIGH)
        
      
def dim_down(): 
    flash = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","capture_mode","flash") 
    dimmer_pwm.start(100)
    for duty_cycle in range(99, 0, -1):
        dimmer_pwm.ChangeDutyCycle(duty_cycle)
        time.sleep(flash / 100)
    dimmer_pwm.start(0)
    #GPIO.output(dimmer_pin, GPIO.LOW)


def LepiLED_start(display_mode = "show"):
    flash = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","capture_mode","flash") 
    if display_mode == "show":
        display_text_and_image("","UV","","/home/Ento/LepmonOS/startsequenz/Warnung_UV.png",2)
    print("dimme UV LED hoch")
    LepiLed_pwm.start(0)
    for duty_cycle in range(0, 99, 1):
        LepiLed_pwm.ChangeDutyCycle(duty_cycle)
        time.sleep(flash / 100)
        LepiLed_pwm.ChangeDutyCycle(100)
    if display_mode == "show":
        show_message("blank", lang="de")
    


def LepiLED_ende(display_mode = "show"):
    flash = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","capture_mode","flash") 
    print("dimme UV LED runter")
    LepiLed_pwm.start(100)
    for duty_cycle in range(99, 0, -1):
        LepiLed_pwm.ChangeDutyCycle(duty_cycle)
        time.sleep(flash / 100)
        LepiLed_pwm.ChangeDutyCycle(0)
    LepiLed_pwm.start(0)
    if display_mode == "show":
        show_message("blank", lang="de")

if __name__ == "__main__":
    print("Funktionen zum Steuern der LEDs")
    dim_up()
    time.sleep(1)
    dim_down()
    time.sleep(1)
    LepiLED_start()
    LepiLED_ende()     
    