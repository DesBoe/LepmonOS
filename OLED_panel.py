from PIL import ImageFont, ImageDraw, Image
from luma.core.interface.serial import i2c
from luma.core.render import canvas
from luma.oled.device import sh1106
import time
import os
from GPIO_Setup import *
from hardware import get_hardware_version
from messages import MESSAGE_REGISTER 

print("Loading Font from :", os.path.join(os.path.dirname(__file__), 'FreeSans.ttf'))
oled_font = ImageFont.truetype(os.path.join(os.path.dirname(__file__), 'FreeSans.ttf'), 14)

# OLED-Setup
Display = i2c(port=1, address=0x3C)
try:
    oled = sh1106(Display)
except:
    pass

hardware = get_hardware_version()
if hardware == "Pro_Gen_1":
    oled.rotate = 2
    
oled_font = ImageFont.truetype('FreeSans.ttf', 14)

def display_text(line1, line2, line3, sleeptime =0):
    try:
        with canvas(oled) as draw:
            draw.rectangle(oled.bounding_box, outline="black", fill="black")
            draw.text((0, 5), line1, font=oled_font, fill="white")
            draw.text((0, 25), line2, font=oled_font, fill="white")
            draw.text((0, 45), line3, font=oled_font, fill="white")
        time.sleep(sleeptime) 
    except Exception as e:
        print(f"Error displaying text on OLED: {e}")  
        for _ in range(3):
            turn_on_led("rot")
            time.sleep(0.25)
            turn_off_led("rot")
            time.sleep(0.25)      


def display_text_and_image(line1, line2, line3, image_path,sleeptime =0):
    """
    Zeigt links drei Zeilen Text und rechts ein Bild (64x64 px) auf dem OLED an.
    """
    try:
        logo = Image.open(image_path).convert("1").resize((64, 64))
        with canvas(oled) as draw:
            # Hintergrund löschen
            draw.rectangle(oled.bounding_box, outline="black", fill="black")
            draw.bitmap((oled.width - 64, 0), logo, fill=1)
            draw.text((3, 5), line1, font=oled_font, fill="white")
            draw.text((3, 25), line2, font=oled_font, fill="white")
            draw.text((3, 45), line3, font=oled_font, fill="white")
            time.sleep(sleeptime)
    except Exception as e:
        print(f"Error displaying text on OLED: {e}")        
        for _ in range(3):
            turn_on_led("rot")
            time.sleep(0.25)
            turn_off_led("rot")
            time.sleep(0.25)        
    
def display_text_with_arrows(line1, line2, line3=None, x_position=None, sleeptime=0):
    try:
        with canvas(oled) as draw:
            draw.rectangle(oled.bounding_box, outline="black", fill="black")
            draw.text((3, 5), line1, font=oled_font, fill="white")
            draw.text((3, 25), line2, font=oled_font, fill="white")
            draw.text((3, 45), line3 if line3 else "", font=oled_font, fill="white")
            draw.text((110, 5), "▲", font=oled_font, fill="white")
            draw.text((110, 25), "→", font=oled_font, fill="white")
            draw.text((110, 45), "▼", font=oled_font, fill="white")
            # Nur das x an der gewünschten Position anzeigen
            if x_position is not None:
                y0 = 38  # Zeile 3, ggf. anpassen
                draw.text((x_position, y0), "x", font=oled_font, fill="white")
        time.sleep(sleeptime)    
    except Exception as e:
        print(f"Error displaying text on OLED: {e}")
        for _ in range(3):
            turn_on_led("rot")
            time.sleep(0.25)
            turn_off_led("rot")
            time.sleep(0.25) 
            
            
            
def show_message(code: str, lang: str = "de", **values):
    """
    Zeigt eine vordefinierte Nachricht an.
    code  : Schlüssel im MESSAGE_REGISTER
    lang  : 'de', 'en', 'es' ...
    values: optionale Platzhalter-Werte, z.B. user="Anna"
    """
    try:
        entry = MESSAGE_REGISTER[code]
    except KeyError:
        print(f"Unbekannter Nachrichtencode: {code}")
        return

    if lang not in entry:
        print(f"Sprache {lang} nicht gefunden, nutze 'de'.")
        lang = "de"

    lines = [line.format(**values) for line in entry[lang]]
    sleeptime = entry.get("sleep", 0)

    while len(lines) < 3:
        lines.append("")

    display_text(lines[0], lines[1], lines[2], sleeptime)
    
    
    
def show_message_with_arrows(code: str, lang: str = "de", x_position=None, **values):
    try:
        entry = MESSAGE_REGISTER[code]
    except KeyError:
        print(f"Unbekannter Nachrichtencode: {code}")
        return

    if lang not in entry:
        print(f"Sprache {lang} nicht gefunden, nutze 'de'.")
        lang = "de"

    lines = [line.format(**values) for line in entry[lang]]
    sleeptime = entry.get("sleep", 0)

    while len(lines) < 3:
        lines.append("")

    display_text_with_arrows(
        lines[0], lines[1], lines[2],
        x_position=x_position,
        sleeptime=sleeptime
    )
    
if __name__ == "__main__":
    print("Zeige Testnachricht auf OLED")
    display_text("Hallo Nutzer*in", "Dies ist eine Test-", "nachricht auf OLED", sleeptime=5)           