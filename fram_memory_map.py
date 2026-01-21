from tabulate import tabulate

FRAM_MEMORY_MAP = {
#### Attiny Data####    
    (0x0000, 0x000F): {
        "size": 16,
        "description": "Power_ON_Timestamp",
        "type": "Label"
    },    
    (0x0010, 0x002F): {
        "size": 32,
        "description": "Power_ON_Timestamp",
        "type": "ATTINY"
    },
    (0x0030, 0x003F): {
        "size": 16,
        "description": "Power_OFF_Timestamp",
        "type": "Label"
    },
    (0x0040, 0x005F): {
        "size": 32,
        "description": "Power_OFF_Timestamp",
        "type": "ATTINY"
    },
    (0x0060, 0x006F): {
        "size": 16,
        "description": "Status",
        "type": "Label"
    },
    (0x0070, 0x007F): {
        "size": 16,
        "description": "Platzhalter,",
        "type": "ATTINY"
    },
    (0x0070, 0x00FF): {
        "size": 144,
        "description": "FREE",
        "type": "ATTINY"
    },
#### Raspi Data ####
####Setup Prozess####    
    (0x0100, 0x010F): {
        "size": 16,
        "description": "Serialnumber",
        "type": "Label"
    },
    (0x0110, 0x011F): {
        "size": 16,
        "description": "Serialnumber",
        "type": "Setup Prozess"
    },      
    (0x0120, 0x012F): {
        "size": 16,
        "description": "ARNI-Generation",
        "type": "Label"
    },
    (0x0130, 0x013F): {
        "size": 16,
        "description": "ARNI-Generation",
        "type": "Setup Prozess"
    },
    (0x0140, 0x014F): {
        "size": 16,
        "description": "Backplane_Version",
        "type": "Label"
    },
   (0x0150, 0x015F): {
        "size": 16,
        "description": "Backplane_Version",
        "type": "Setup Prozess"
    },
    (0x0160, 0x016F): {
        "size": 16,
        "description": "Lieferdatum_an_PMJ",
        "type": "Label"
    },
    (0x0170, 0x017F): {
        "size": 16,
        "description": "Lieferdatum_an_PMJ",
        "type": "Setup Prozess"
    },
#### Laufzeit Daten ####
    (0x0300, 0x030E): {
        "size": 16,
        "description": "Boot_counter",
        "type": "Label"
    },
    (0x0310, 0x031F): {
        "size": 16,
        "description": "Boot_counter",
        "type": "RPI"
    },
    (0x0320, 0x032F): {
        "size": 15,
        "description": "User_Interface_counter",
        "type": "Label"
    },
    (0x0330, 0x033F): {
        "size": 16,
        "description": "User_Interface_counter",
        "type": "RPI"
    },
    (0x0340, 0x034E): {
        "size": 16,
        "description": "total_runtime",
        "type": "Label"
    },
    (0x0350, 0x035F): {
        "size": 16,
        "description": "total_runtime_Value",
        "type": "RPI"
    },
    (0x0360, 0x036F): {
        "size": 16,
        "description": "timestamp_last_start",
        "type": "Label"
    },
    (0x0370, 0x037F): {
        "size": 16,
        "description": "timestamp_last_start",
        "type": "RPI"
    },
    (0x0380, 0x038F): {
        "size": 16,
        "description": "Gigabytes_free_at_start",
        "type": "Label"
    },
    (0x0390, 0x039F): {
        "size": 16,
        "description": "Gigabytes_free_at_start",
        "type": "RPI"
    },
#### Power Management ####    
    (0x03A0, 0x03AF): {
        "size": 16,
        "description": "Power_supply_mode",
        "type": "Label"
    },
    (0x03B0, 0x03BF): {
        "size": 16,
        "description": "Power_supply_mode",
        "type": "RPI"
    },
#### Lepmon Code Standort Daten ####
    (0x03C0, 0x03CF): {
        "size": 16,
        "description": "latitude",
        "type": "RPI"
    },
    (0x03D0, 0x03DF): {
        "size": 16,
        "description": "Pol",
        "type": "RPI"
    },
    (0x03E0, 0x03EF): {
        "size": 16,
        "description": "longitude",
        "type": "RPI"
    },
    (0x03F0, 0x03FF): {
        "size": 16,
        "description": "Block",
        "type": "RPI"
    },
    (0x0400, 0x045F): {
        "size": 96,
        "description": "Block",
        "type": "RPI"
    },
    
    (0x0460, 0x046F): {
        "size": 16,
        "description": "Zeitumstellung",
        "type": "Label"
    },
    (0x0470, 0x048F): {
        "size": 32,
        "description": "Daylights Saving timestamp+controllbit",
        "type": "RPI"
    },
    
    
    (0x0490, 0x049F): {
        "size": 16,
        "description": "Land",
        "type": "Label"
    },
    
    (0x04A0, 0x04BF): {
        "size": 32,
        "description": "Land",
        "type": "RPI"
    },
    (0x04C0, 0x04CF): {
        "size": 16,
        "description": "Provinz",
        "type": "Label"
    },
    (0x04D0, 0x04DF): {
        "size": 16,
        "description": "Provinz",
        "type": "RPI"
    },
    (0x04E0, 0x04EF): {
        "size": 16,
        "description": "Stadt",
        "type": "Label"
    },
    (0x04F0, 0x04FF): {
        "size": 16,
        "description": "Stadt",
        "type": "RPI"
    },
#### Software Version ####
    (0x0500, 0x050F): {
        "size": 16,
        "description": "Software_Information",
        "type": "Label"
    },
    (0x0510, 0x051F): {
        "size": 16,
        "description": "Software_Date",
        "type": "RPI"
    },
    (0x0520, 0x055F): {
        "size": 64,
        "description": "Software_Version",
        "type": "RPI"
    },
    (0x0560, 0x056F): {
        "size": 16,
        "description": "new_package + controlbit",
        "type": "RPI"
    }, 
    (0x0570, 0x057F): {
        "size": 16,
        "description": "random",
        "type": "Setup_Prozess"
    }, 

    (0x0580, 0x058F): {
        "size": 64,
        "description": "FREE"
    }, 
        
    (0x0600, 0x060F): {
        "size": 16,
        "description": "language",
        "type": "Label"
    },     

    (0x0610, 0x061F): {
        "size": 16,
        "description": "language",
        "type": "RPI"
    }, 
    
    (0x0620, 0x062F): {
        "size": 16,
        "description": "images_expected",
        "type": "Label"
    },
    
    (0x0630, 0x063F): {
        "size": 16,
        "description": "images_expected",
        "type": "RPI"
    },
        
    (0x0640, 0x064F): {
        "size": 16,
        "description": "images_count",
        "type": "Label"
    }, 
        
    (0x0650, 0x065F): {
        "size": 16,
        "description": "images_count",
        "type": "RPI"
    },
    (0x0660, 0x067F): {
        "size": 32,
        "description": "FREE",
        "type": "Label"
    },
    (0x0680, 0x068F): {
        "size": 16,
        "description": "current_Exp_Gain",
        "type": "Label"
    },
    (0x0690, 0x069F): {
        "size": 16,
        "description": "current_Exp_Gain",
        "type": "RPI"
    },
    (0x06A0, 0x077F): {
        "size": 256,
        "description": "FREE",
        "type": "RPI"
    },
    (0x0780, 0x078F): {
        "size": 16,
        "description": "focus_restart + controlbit",
        "type": "Setup_Prozess"
    }, 
       (0x0790, 0x079F): {
        "size": 16,
        "description": "Control_Night",
        "type": "Label"
    },   
       (0x07A0, 0x07AF): {
        "size": 16,
        "description": "Control_Night",
        "type": "RPI"
    },   
       (0x07B0, 0x07BF): {
        "size": 16,
        "description": "Control_End",
        "type": "Label"
    },   
       (0x07C0, 0x07CF): {
        "size": 16,
        "description": "Control_End",
        "type": "RPI"
    },
   
    (0x07D0, 0x07DF): {
        "size": 16,
        "description": "RPI_activity",
        "type": "Label"
    },
    (0x07E0, 0x07FF): {
        "size": 32,
        "description": "RPI_activity",
        "type": "RPI"
    },
    (0x0800, 0x080F): {
        "size": 16,
        "description": "aktueller_Fehler",
        "type": "Label"
    },
    (0x0810, 0x081F): {
        "size": 16,
        "description": "aktueller_Fehler_Code",
        "type": "RPI"
    },
    (0x0820, 0x082F): {
        "size": 16,
        "description": "Fehlerfrequenz_Tabelle",
        "type": "Label"
    },
    (0x0830, 0x083F): {
        "size": 16,
        "description": "Err  1 Kamera",
        "type": "Label"
    },
    (0x0840, 0x084F): {
        "size": 16,
        "description": "Err  1 Kamera",
        "type": "RPI"
    },
    (0x0850, 0x085F): {
        "size": 16,
        "description": "Err  2 Fokus",
        "type": "Label"
    },
    (0x0860, 0x086F): {
        "size": 16,
        "description": "Err  2 Fokus",
        "type": "RPI"
    },
    (0x0870, 0x087F): {
        "size": 16,
        "description": "Err  3 USB",
        "type": "Label"
    },
    (0x0880, 0x088F): {
        "size": 16,
        "description": "Err  3 USB",
        "type": "RPI"
    },
    (0x0890, 0x089F): {
        "size": 16,
        "description": "Err  4 Lichtsensor",
        "type": "Label"
    },
    (0x08A0, 0x08AF): {
        "size": 16,
        "description": "Err  4 Lichtsensor",
        "type": "RPI"
    },
    (0x08B0, 0x08BF): {
        "size": 16,
        "description": "Err  5 Umweltsensor",
        "type": "Label"
    },
    (0x08C0, 0x08CF): {
        "size": 16,
        "description": "Err  5 Umweltsensor",
        "type": "RPI"
    },
    (0x08D0, 0x08DF): {
        "size": 16,
        "description": "Err  6 Innen-Temperatur",
        "type": "Label"
    },
    (0x08E0, 0x08EF): {
        "size": 16,
        "description": "Err  6 Innen-Temperatur",
        "type": "RPI"
    },
    (0x08F0, 0x08FF): {
        "size": 16,
        "description": "Err  7 Stromsensor",
        "type": "Label"
    },
    (0x0900, 0x090F): {
        "size": 16,
        "description": "Err  7 Stromsensor",
        "type": "RPI"
    },
    (0x0910, 0x091F): {
        "size": 16,
        "description": "Err  8 Hardware Uhr",
        "type": "Label"
    },
    (0x0920, 0x092F): {
        "size": 16,
        "description": "Err  8 Hardware Uhr",
        "type": "RPI"
    },
    (0x0930, 0x093F): {
        "size": 16,
        "description": "Err  9 FRAM",
        "type": "Label"
    },
    (0x0940, 0x094F): {
        "size": 16,
        "description": "Err  9 FRAM",
        "type": "RPI"
    },
    (0x0950, 0x095F): {
        "size": 16,
        "description": "Err 10 Logging",
        "type": "Label"
    },
    (0x0960, 0x096F): {
        "size": 16,
        "description": "Err 10 Logging",
        "type": "RPI"
    },
    (0x0970, 0x097F): {
        "size": 16,
        "description": "Err 11 Checksumme",
        "type": "Label"
    },
    (0x0980, 0x098F): {
        "size": 16,
        "description": "Err 11 Checksumme",
        "type": "RPI"
    },
    (0x0990, 0x099F): {
        "size": 16,
        "description": "Err 12 Beleuchtungs LED",
        "type": "Label"
    },
    (0x09A0, 0x09AF): {
        "size": 16,
        "description": "Err 12 Beleuchtungs LED",
        "type": "RPI"
    },
    (0x09B0, 0x09BF): {
        "size": 16,
        "description": "Err 13 Metadaten Tabelle",
        "type": "Label"
    },
    (0x09C0, 0x09CF): {
        "size": 16,
        "description": "Err 13 Metadaten Tabelle",
        "type": "RPI"
    },
    (0x09D0, 0x09BD): {
        "size": 16,
        "description": "Err 14 Foto Sanity Check",
        "type": "Label"
    },
    (0x09E0, 0x09EF): {
        "size": 16,
        "description": "Err 14 Foto Sanity Check",
        "type": "RPI"
    },    
    (0x09F0, 0x1BFF): {
        "size": 4624,
        "description": "FREE",
        "type": "RPI"
    },    
    (0x1C00, 0x1FFF): {
        "size": 1024,
        "description": "FREE",
        "type": "Production"
    }
}

def print_fram_memory_map_tab():
    table = []
    for (start, end), info in FRAM_MEMORY_MAP.items():
        # Prüfe, ob "type" im Info-Dict vorhanden ist, sonst leeres Feld
        regime = info.get("type", "")
        table.append([f"0x{start:04X}", f"0x{end:04X}", info['size'], info['description'], regime])
    print(tabulate(table, headers=["Start", "Ende", "Größe", "Beschreibung", "Regime"], tablefmt="github"))
    
    
    


if __name__ == "__main__":

    print_fram_memory_map_tab()