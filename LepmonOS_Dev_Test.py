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
        '''
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
            
            

                        



