from hardware import get_hardware_version
from OLED_panel import display_text_and_image

hardware = get_hardware_version()
print(f"Hardware Version: {hardware}")

if hardware in ["Pro_Gen_2", "Pro_Gen_3"]:
        display_text_and_image("switch", "always", "on", "/home/Ento/LepmonOS/startsequenz/Knopf_An_Aus.png", sleeptime=5)
if hardware in ["Pro_Gen_4", "CSS_Gen_1"]:
    for _ in range(3):
        display_text_and_image("switch", "always", "on", "/home/Ento/LepmonOS/startsequenz/Knopf_An_Aus.png", sleeptime=2)
        display_text_and_image("power", "safe", "mode", "/home/Ento/LepmonOS/startsequenz/Knopf_An_An.png", sleeptime=2)