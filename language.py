from fram_operations import *
from json_read_write import *
from OLED_panel import *
from GPIO_Setup import turn_on_led
import time

def get_language():
    try:
        lang = read_fram(0x0610,16).replace('\x00', '').strip()
        if lang not in ["de", "en", "es"]:
            raise ValueError("Ungültige Sprache im FRAM")
    except Exception as e:
        lang = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","general","language")
    return lang

def set_language():
    lang_old = get_language()
    user_selection_language = False
    new_language = None
    
    
    show_message("lang_01", lang=lang_old)
    turn_on_led("blau")
    print("mit dem HMI neue Sprache auswählen\nOben = Sprache ändern\nUnten = aktuelle Sprache behalten")
    while user_selection_language == False:
        time.sleep(.05)

        if button_pressed("unten"):
            user_selection_language = True
            time.sleep(1)
            return lang_old

        elif button_pressed("oben"):
            user_selection_language = True
            display_text("Deutsch","English","Español")
            show_message_with_arrows("lang_02", lang=lang_old)
            while new_language == None:
                if button_pressed("oben"):
                    new_language = "de"
                    show_message_with_arrows("lang_de", lang=new_language)
                    print(f"neue Sprache: {new_language}")

                elif button_pressed("rechts"):
                    new_language = "en"
                    show_message_with_arrows("lang_en", lang=new_language)
                    print(f"neue Sprache: {new_language}")
                    
                    
                elif button_pressed("unten"):
                    new_language = "es"
                    show_message_with_arrows("lang_es", lang=new_language)
                    print(f"neue Sprache: {new_language}")
                    
                time.sleep(.05)
                
            write_value_to_section("/home/Ento/LepmonOS/Lepmon_config.json", "general", "language", new_language)
            turn_off_led("blau")  
            try:  
                write_fram(0x0610, new_language)
            except Exception as e:
                print("neue Sprache nicht im Fram gespeichert")    
            time.sleep(1)
            return new_language    
        
        
        
if __name__ == "__main__":
    set_language()        