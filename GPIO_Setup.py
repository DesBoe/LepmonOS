import RPi.GPIO as GPIO
import time
import threading
GPIO.setwarnings(False)
from hardware import get_hardware_version
hardware = get_hardware_version()

# Terminal-Eingabe für Buttons simulieren
terminal_button_input = None
def terminal_input_listener():
    global terminal_button_input
    while True:
        user_input = input()
        terminal_button_input = user_input.strip().lower()

# Starte den Listener-Thread beim Import
threading.Thread(target=terminal_input_listener, daemon=True).start()

# Definiere die Pin-Nummern für LEDs und Knöpfe
if hardware == "Pro_Gen_1":
    LED_PINS = {
    'gelb': 27,    
    'blau': 22 ,    
    'rot': 17,      
    #'Kamera':5,
    'Heizung': 13
}

BUTTON_PINS = {
    'oben': 24,     
    'unten': 23,    
    'rechts': 7,  
    'enter': 8    
}

if hardware == "Pro_Gen_2" or hardware == "Pro_Gen_3":
    LED_PINS = {
        'gelb': 22,    
        'blau': 6,     
        'rot': 17,     
        'Heizung': 27
    }

    BUTTON_PINS = {
        'oben': 23,     
        'unten': 24,    
        'rechts': 8,  
        'enter': 7    
    }

# Setup der GPIOs
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

# LEDs als Ausgang und Knöpfe als Eingang setzen
for pin in LED_PINS.values():
    GPIO.setup(pin, GPIO.OUT)
    GPIO.output(pin, GPIO.LOW)  # LEDs aus zu Beginn

for pin in BUTTON_PINS.values():
    GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # Knöpfe als Eingänge mit Pull-up-Widerstand

# PWM für LEDs einrichten
led_pwm = {}
for color, pin in LED_PINS.items():
    pwm = GPIO.PWM(pin, 1000)  # PWM bei 1kHz
    pwm.start(0)  # Startwert 0 (LEDs aus)
    led_pwm[color] = pwm

# Funktion, um die Helligkeit der LEDs zu ändern (Dimmung)
def dim_led(color, brightness):
    """Dimmt die angegebene LED (z.B. 'gelb', 'blau', 'rot')."""
    if color in led_pwm:
        led_pwm[color].ChangeDutyCycle(brightness)  # Helligkeit zwischen 0 und 100

# Funktion, um den Status eines Knopfs abzufragen
def button_pressed(button_name):
    """
    Überprüft, ob der angegebene Knopf gedrückt wurde (GPIO oder Terminal).

    :param button_name: Name des Knopfes ('oben', 'unten', 'rechts', 'enter').
    :return: True, wenn der Knopf gedrückt wurde, sonst False.
    :raises ValueError: Wenn der angegebene Knopfname nicht existiert.
    """
    global terminal_button_input
    if button_name not in BUTTON_PINS:
        available_buttons = ", ".join(BUTTON_PINS.keys())
        raise ValueError(f"Ungültiger Knopfname '{button_name}'. Verfügbare Knöpfe: {available_buttons}")

    # GPIO-Check
    if GPIO.input(BUTTON_PINS[button_name]) == GPIO.LOW:
        return True

    # Terminal-Check
    if terminal_button_input == button_name.lower():
        terminal_button_input = None  # zurücksetzen
        return True
    time.sleep(.025)

    return False

def turn_on_led(color):
    """Schaltet die angegebene LED ein (volle Helligkeit)."""
    dim_led(color, 100)

def turn_off_led(color):
    """Schaltet die angegebene LED aus."""
    dim_led(color, 0)


if __name__ == "__main__":
    print("Teste GPIO-Setup... Beobachte HMI")
    time.sleep(2)
    turn_on_led("rot")
    time.sleep(.33)
    turn_on_led("blau")
    time.sleep(.33)
    turn_on_led("gelb")
    time.sleep(.33)
    turn_off_led("rot")
    time.sleep(.33)
    turn_off_led("blau")
    time.sleep(.33)
    turn_off_led("gelb")
    
    

