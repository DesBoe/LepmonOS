import time
# Zentrales Nachrichten-Register für das OLED-Display - Struktur
## code: { 
#       "sleep": Sekunden,
#       "de": ("Zeile1","Zeile2","Zeile3"),
#       "en": (...), 
#       "es": (...)
# },

#######################################################################
########## auch in Bedienungsanleitungsordner aktuell halten! #########
#######################################################################


MESSAGE_REGISTER = {
    ### Dev ###
    "dev_1": {
        "sleep": 1,
        "de":("###############","## Test Version ##","###############"),
        "en":("###############","## Test Version ##","###############"),
        "es":("###############","#Versión de Test#","###############")
    },
    ### device ###
    "device_1": {
        "sleep": 1,
        "de": ("Version: {hardware}", "SN: {sn}", "Firmware: {version}"),
        "en": ("Version: {hardware}", "SN: {sn}", "Firmware: {version}"),
        "es": ("Versión: {hardware}", "SN: {sn}", "Firmware: {version}")
    },
    ### hmi ### 
    "hmi_01": {
        "sleep": 0,
        "de": ("Menü öffnen", "bitte Enter drücken", "(linke Taste)"),
        "en": ("Menu open", "please press Enter", "(left button)"),
        "es": ("Abrir menú", "por favor presione Enter", "(botón izquierdo)")
    },
    "hmi_02": {
        "sleep": 0,
        "de": ("Menü öffnen", "bitte Enter drücken", "(rechte Taste)"),
        "en": ("Menu open", "please press Enter", "(right button)"),
        "es": ("Abrir menú", "por favor presione Enter", "(botón derecho)")
    },
    "hmi_03": {
        "sleep": 0,
        "de": ("Eingabe Menü","geöffnet", ""),
        "en": ("Input menu","opened",""),
        "es": ("Menú de entrada","abierto","")
    },    
       "hmi_06": {
        "sleep": 1,
        "de": ("Stromversorgung:","▲= Solar →= zurück","▼= Netz"),
        "en": ("Power supply:","▲= Solar","▼= Grid","→= back"),
        "es": ("Fuente de energía:","▲= Solar","▼= Red","→= atrás")
    },          
    "hmi_07": {
        "sleep": 2,
        "de": ("Stromversorgung","Solar", ""),
        "en": ("Power supply","Solar",""),
        "es": ("Fuente de energía","Solar","")
    },
    "hmi_08": {
        "sleep": 2,
        "de": ("Stromversorgung","Netz", ""),
        "en": ("Power supply","Grid",""),
        "es": ("Fuente de energía","Red","")
    },
    "hmi_09": {
        "sleep": 1,
        "de": ("USB Daten löschen?","▲ = ja     → = zurück","▼ = nein"),
        "en": ("Erase USB data?","▲ = yes     → = back","▼ = no"),
        "es": ("¿Borrar datos USB?","▲ = sí     → = atrás","▼ = no")
    },
    "hmi_10": {
        "sleep": 1,
        "de": ("USB Stick wird gelöscht","bitte warten",""),
        "en": ("Erasing USB data","please wait",""),
        "es": ("Borrando datos USB","por favor espere","")
    },
    "hmi_11": {
        "sleep": 1,
        "de": ("USB Stick gelöscht","",""),
        "en": ("USB data deleted","",""),
        "es": ("Datos USB borrados","","")
    },
    "hmi_12": {
        "sleep": 2,
        "de": ("USB Stick","nicht gelöscht",""),
        "en": ("USB data","not deleted",""),
        "es": ("Datos USB","no borrados","")
    },
    "hmi_13": {
        "sleep": 1,
        "de": ("Scheibe heizen?","▲ = ja     → = zurück","▼ = nein"),
        "en": ("Heat window?","▲ = yes     → = back","▼ = no"),
        "es": ("¿Calentar el vidrio?","▲ = sí     → = atrás","▼ = no")
    },  
    "hmi_14": {
        "sleep": 1,
        "de": ("Heizung aktiviert","für 15 min","",),
        "en": ("Heater on","for 15 min",""),
        "es": ("Calefacción activada","por 15 min","")
    },  
    "hmi_15": {
        "sleep": 1,
        "de": ("Heizung bleibt","ausgeschaltet",""),
        "en": ("Heater remains","off",""),
        "es": ("Calefacción","apagada","")
    },  
    "hmi_16": {
        "sleep": 1,
        "de": ("Datum / Uhrzeit:","▲ = aktualisieren","▼ = bestätigen"),
        "en": ("Date / Time:","▲ = update","▼ = confirm"),
        "es": ("Fecha / Hora:","▲ = actualizar","▼ = confirmar")
    },   
    "hmi_17": {
        "sleep": 0.1,
        "de": ("{date} {time}","▲ = neu  → = zurück","▼ = ok"),
        "en": ("{date}","{time}","▲ = new  → = back","▼ = ok"),
        "es": ("{date}","{time}","▲ = nuevo  → = atrás","▼ = ok")
    },  
    "hmi_18": {
        "sleep": 1,
        "de": ("Koordinaten:","▲ = aktualisieren","▼ = bestätigen"),
        "en": ("Coordinates:","▲ = update","▼ = confirm"),
        "es": ("Coordenadas:","▲ = actualizar","▼ = confirmar")
    },  
    "hmi_19": {
        "sleep": 0.1,
        "de": ("N-S: {latitude}", "O-W: {longitude}","▲neu ▼ok →zurück"),
        "en": ("N-S: {latitude}","E-W: {longitude}","▲=new ▼=ok →=back"),
        "es": ("N-S: {latitude}","E-O: {longitude}","▲=nuevo ▼=ok →=atrás")
    },  
    "hmi_20": {
        "sleep": 0.25,
        "de": ("LEPMON-Code:","▲ = aktualisieren","▼ = bestätigen"),
        "en": ("LEPMON-Code:","▲ = update","▼ = confirm"),
        "es": ("LEPMON-Code::","▲ = actualizar","▼ = confirmar")
    },  
    "hmi_21": {
        "sleep": 0.1,
        "de": ("Provinz:{provinz}","Kreis: {Kreiscode}", "▲ = neu  ▼ = ok"),
        "en": ("Province: {provinz}","District: {Kreiscode}","▲ = new  ▼ = ok"),
        "es": ("Provincia: {provinz}","Distrito: {Kreiscode}","▲ = nuevo  ▼ = ok")
    },    
    "hmi_22": {
        "sleep": 2,
        "de": ("Code unverändert","fahre fort",""),
        "en": ("Code unchanged","continue",""),
        "es": ("Código sin cambios","continuar","")
    },
    "hmi_23": {
        "sleep": 3,
        "de": ("Code geändert","ARNI übernimmt","Änderungen"),
        "en": ("Code changed","ARNI adopts","changes"),
        "es": ("Código cambiado","ARNI adopta","cambios")
    },
    "hmi_24": {
        "sleep": 2,
        "de": ("Code nicht geändert","fahre fort",""),
        "en": ("Code not changed","continue",""),
        "es": ("Código no cambiado","continuar","")
    },
    "hmi_25": {
        "sleep": 0,
        "de": ("▲ = Testlauf starten","","→ = zurück"),
        "en": ("▲ = Start test run","","→ = back"),
        "es": ("▲ = Iniciar prueba","","→ = atrás")
    },
    "hmi_26": {
        "sleep": 1,
        "de": ("Kamera Test","",""),
        "en": ("Camera test","",""),
        "es": ("Prueba de cámara","","")
    },
    "hmi_27": {
        "sleep": 3,
        "de": ("Kamera Test","Kamera nicht","verfügbar starte neu"),
        "en": ("Camera test","camera not","available - restart"),
        "es": ("Prueba de cámara","cámara no","disponible - reiniciar")
    },
    "hmi_28": {
        "sleep": 1,     
        "de": ("Kamera Test","erfolgreich","beendet"),
        "en": ("Camera test","successful","finished"),
        "es": ("Prueba de cámara","finalizada","con éxito")
    },
    "hmi_29": {
        "sleep": 3,
        "de": ("USB Speicher","gesamt: {total_space} GB","frei: {free_space} GB"),
        "en": ("USB storage","total: {total_space} GB","available: {free_space} GB"),
        "es": ("Almacenamiento USB","total: {total_space} GB","libre: {free_space} GB")
    },
    "hmi_30": {
        "sleep": 3,
        "de": ("USB Speicher","nicht erkannt","Prüfe Anschluss"),
        "en": ("USB storage","not detected","check connection"),
        "es": ("Almacenamiento USB","no detectado","verifique conexión")
    },
    "hmi_31": {
        "sleep": 3,
        "de": ("USB Speicher","fast voll","leeren"),
        "en": ("USB storage","almost full","delete"),
        "es": ("Almacenamiento USB","casi lleno", "vaciar")
    },
    "hmi_32": {
        "sleep": 1,
        "de": ("USB Speicher","OK",""),
        "en": ("USB storage","OK",""),
        "es": ("Almacenamiento USB","OK","")
    },  
    "hmi_33": {
        "sleep": 2,
        "de": ("Sonne:", "Untergang: {sunset}", "Aufgang:    {sunrise}"),
        "en": ("Sunset:  {sunset}","Sunrise: {sunrise}",""),
        "es": ("Atardecer: {sunset}","Amanecer: {sunrise}","")
    },      
    "hmi_35": {
        "sleep": 1,
        "de": ("Testlauf beendet","Übernehme neuen","LEPMON-Code"),
        "en": ("Test run finished","adopting new","LEPMON-Code"),
        "es": ("Prueba terminada","adoptando nuevo","LEPMON-Code")
    },   
    "hmi_36": {
        "sleep": 2,
        "de": ("Testlauf beendet","Deckel","schließen"),
        "en": ("Test run finished","close","lid"),
        "es": ("Prueba terminada","cierre","la cubierta")
    },               
    "hmi_gps_check_1": {
        "sleep": 1,
        "de": ("Prüfe Land/","Provinz eingebener","Koordinaten"),
        "en": ("Checking country/","province of entered","coordinates"),
        "es": ("Comprobando país/","provincia de las","coordenadas ingresadas")
    },
    "hmi_gps_check_2": {
        "sleep": 1,
        "de": ("Land: {country_name}","Provinz: {region_name}","▲ = neu  ▼ = ok"),
        "en": ("Country: {country_name}","Province: {region_name}","▲ = new  ▼ = ok"),
        "es": ("País: {country_name}","Provincia: {region_name}","▲ = nuevo  ▼ = ok")
    },
    
    "hmi_sensor_check_1": {
        "sleep": 3,
        "de": ("teste Sensoren","erneut","warte..."),
        "en": ("test sensors", "again", "waiting..."),
        "es": ("probar sensores", "de nuevo", "esperando...")
    },  
    "hmi_sensor_check_2": {
        "sleep": 3,
        "de": ("Alle Sensoren","gefunden",""),
        "en": ("All sensors", "present", ""),
        "es": ("Todos los sensores", "encontrados", "")
    }, 
    "hmi_sensor_check_3": {
        "sleep": 3,
        "de": ("Sensor fehlt","weiterhin","fahre fort"),
        "en": ("Sensor still", "missing", "continue anyways"),
        "es": ("Falta el sensor", "todavía", "continuar")
    },  
    
    ### updater ###
    "update_3": {
        "sleep": 2,
        "de": ("Update-Ordner","gefunden",""),
        "en": ("Update folder","found",""),
        "es": ("Carpeta de actualización","encontrada","")
    },   
    "update_4": {
        "sleep": 2,
        "de": ("Update-Ordner","nicht gefunden",""),
        "en": ("Update folder","not found",""),
        "es": ("Carpeta de actualización","no encontrada","")
    },   
    "update_5": {
        "sleep": 2,
        "de": ("Schlüsseldatei","nicht gefunden",""),
        "en": ("Key file","not found",""),
        "es": ("Archivo de seguridad","no encontrado","")
    },   
    "update_6": {
        "sleep": 1,
        "de": ("Schlüsseldatei","gefunden",""),
        "en": ("Key file","found",""),
        "es": ("Archivo de seguridad","encontrado","")
    },   
    "update_7": {
        "sleep": 0,
        "de": ("neue Version","nicht gefunden",""),
        "en": ("New version","not found",""),
        "es": ("Nueva versión","no encontrada","")
    },   
    "update_8": {
        "sleep": 2,
        "de": ("Software Version","bereits aktuell",""),
        "en": ("Software version","already up to date",""),
        "es": ("Versión de software","actualizada","")
    },   
    "update_9": {
        "sleep": 2,
        "de": ("Downgrade","nicht erlaubt",""),
        "en": ("Downgrade","not permitted",""),
        "es": ("Volver a la", "versión anterior", "no permitido")
    },   
    "update_10": {
        "sleep": 2,
        "de": ("LepmonOS Update","Starte Update...","warten..."),
        "en": ("LepmonOS update","Starting update...","wait..."),
        "es": ("Actualización de LepmonOS","Iniciando actualización...","espere...")
    },   
    "update_11": {
        "sleep": 1,
        "de": ("Update","wird gestartet",""),
        "en": ("Update","starting",""),
        "es": ("Actualización","iniciando","")
    },   
    "update_12": {
        "sleep": 2,
        "de": ("Update-Ordner","gefunden",""),
        "en": ("Update folder","found",""),
        "es": ("Carpeta de actualización","encontrada","")
    },   
    "update_13": {
        "sleep": 2,
        "de": ("Update-Ordner","nicht gefunden",""),
        "en": ("Update folder","not found",""),
        "es": ("Carpeta de actualización","no encontrada","")
    },   
    "update_14": {
        "sleep": 1,
        "de": ("Update","erfolgreich",""),
        "en": ("Update","successful",""),
        "es": ("Actualización","exitosa","")
    },   
    "update_15": {
        "sleep": 3,
        "de": ("Neue Version:","{version}","{date}"),
        "en": ("New version:","{version}","{date}"),
        "es": ("Nueva versión:","{version}","{date}")
    },   
    "update_16": {
        "sleep": 2,
        "de": ("Update installiert","starte neu",""),
        "en": ("Update installed","restarting",""),
        "es": ("Actualización instalada","reiniciando","")
    },   
    "update_17": {
        "sleep": 3,
        "de": ("Kein Update","durchgeführt","fahre fort"),
        "en": ("No update","performed","continue"),
        "es": ("Sin actualización","realizada","continuar")
    },
    
    ### packages ###
    
    "package_1": {
        "sleep": .1,
        "de": ("package Installation","startet...",""),
        "en": ("package installation","starting...",""),
        "es": ("Instalación de paquetes","iniciando...","")
    },
    "package_2": {
        "sleep": 2,
        "de": ("Alle Pakete","bereits installiert",""),
        "en": ("All packages","already installed",""),
        "es": ("Todos los paquetes","ya instalados","")
    },
    "package_3": {
        "sleep": .1,
        "de": ("Installiere Paket:","{package}","{version}"),
        "en": ("Installing package:","{package}","{version}"),
        "es": ("Instalando paquete:","{package}","{version}")
    },
    "package_4": {
        "sleep": 1,
        "de": ("Installiert:","{package}","{version}"),
        "en": ("Installed:","{package}","{version}"),
        "es": ("Instalado:","{package}","{version}")
    },
    "package_5": {
        "sleep": 1,
        "de": ("versuche", "Standard", "Installation"),
        "en": ("attempting", "standard", "installation"),
        "es": ("intentando", "instalación", "estándar")
    },
    "package_6": {
        "sleep": 1,
        "de": ("Standart Installation","erfolgreich",""),
        "en": ("Standard installation","successful",""),
        "es": ("Instalación estándar","exitosa","")
    },
    "package_7": {
        "sleep": 2,
        "de": ("Alle Pakete","erfolgreich","installiert",""),
        "en": ("All packages","successfully","installed"),
        "es": ("Todos los","paquetes instalados", "con éxito")
    },
        
        
        
        
        
        
    ### lang ###
    "lang_01": {
        "sleep": 0,
        "de": ("Sprache: Deutsch", "ändern?", "▲ = ja  ▼ = nein"),
        "en": ("Language: English","change?","▲ = yes  ▼ = no"),
        "es": ("Idioma: Español","¿cambiar?","▲ = sí  ▼ = no")
    },  
    "lang_02": {
        "sleep": 0,
        "de": ("Deutsch","English","Español"),
        "en": ("Deutsch","English","Español"),
        "es": ("Deutsch","English","Español")
    },    
    "lang_de": {
        "sleep": 2,
        "de": ("Deutsch x","English","Español"),
        "en": ("Deutsch x","English","Español"),
        "es": ("Deutsch x","English","Español")
    },   
    "lang_en": {
        "sleep": 2,
        "de": ("Deutsch","English   x","Español"),
        "en": ("Deutsch","English   x","Español"),
        "es": ("Deutsch","English   x","Español")
    },  
    "lang_es": {
        "sleep": 2,
        "de": ("Deutsch","English","Español x"),
        "en": ("Deutsch","English","Español x"),
        "es": ("Deutsch","English","Español x")
    },    
    
    # focus
    

    "focus_1": {
        "sleep": .5,
        "de": ("Ermittle Belichtung","für Fokussieren","{average_brightness}; {Exposure} ms; {Gain}"),
        "en": ("Determine exposure","for focusing","{average_brightness}; {Exposure} ms; {Gain}"),
        "es": ("Determinar exposición:","para enfocar","{average_brightness}; {Exposure} ms; {Gain}")
    },
    "focus_2": {
        "sleep": 3,
        "de": ("Kamera überlastet", "fokussieren nicht", "beendet"),
        "en": ("Camera overloaded", "focusing not", "finished"),
        "es": ("Cámara sobrecargada", "no enfoque", "finalizado")
    },
    "focus_3": {
        "sleep": 3,
        "de": ("Setze Fokussieren", "nach Neustart", "fort"),
        "en": ("continue focusing", "after restart", ""),
        "es": ("después del reinicio", "continuar", "enfocando")
    },      

    "focus_4": {
        "sleep": 1,
        "de": ("Belichtung gefunden","",""),
        "en": ("Exposure","determined",""),
        "es": ("Exposición","determinada","")
    },    

    "focus_5": {
        "sleep": 3,
        "de": ("fokussieren", "bis Schärfe", "Maximum erreicht"),
        "en": ("Focusing", "until sharpness", "maximum reached"),
        "es": ("Enfocando", "hasta nitidez", "máximo sea alcanzado")
    },   

    "focus_6": {
        "sleep": 2.5,
        "de": ("jetzt Fokusring", "drehen (0.5 - 1 m)","alt:{variance_old} - neu:{variance_new}"),
        "en": ("turn focus","ring (0.5 - 1 m)", "old:{variance_old} - new:{variance_new}"),
        "es": ("gire ahora anillo","de enfoque (0.5 - 1 m)","antiguo:{variance_old} - nuevo:{variance_new}")
    },   
    "focus_7": {
        "sleep": 2,
        "de": ("Nehme Testbild auf","nicht drehen","alt:{variance_old} - neu:{variance_new}"),
        "en": ("Taking test image","do not turn","old:{variance_old} - new:{variance_new}"),
        "es": ("Tomando imagen de prueba","no girar","antiguo:{variance_old} - nuevo:{variance_new}")
    },
    
    "focus_8": {
        "sleep": 2.5,
        "de": ("Bild ist schärfer", "weiter drehen", "alt:{variance_old} - neu:{variance_new}"),
        "en": ("Image is sharper", "turn further", "old:{variance_old} - new:{variance_new}"),
        "es": ("La imagen es más nítida", "gire más", "antiguo:{variance_old} - nuevo:{variance_new}")
    },
    "focus_9": {
        "sleep": 2.5,
        "de": ("Bild ist unschärfer", "zurück drehen", "alt:{variance_old} - neu:{variance_new}"),
        "en": ("Image is blurrier", "turn back", "old:{variance_old} - new:{variance_new}"),
        "es": ("La imagen es más borrosa", "gire hacia atrás", "antiguo:{variance_old} - nuevo:{variance_new}")
    },
    "focus_10": {
        "sleep": 2.5,
        "de": ("Bild gleichbleibend", "keine Änderung", "alt:{variance_old} - neu:{variance_new}"),
        "en": ("Image unchanged", "no change", "old:{variance_old} - new:{variance_new}"),
        "es": ("Imagen sin cambios", "sin cambios", "antiguo:{variance_old} - nuevo:{variance_new}")
    },
    "focus_11": {
        "sleep": 1,
        "de": ("Fokussieren vom","Nutzenden beendet",""),
        "en": ("Focusing ended","by user",""),
        "es": ("Enfoque terminado","por el usuario","")
    },
    "focus_12": {
        "sleep": 4,
        "de": ("Notfallabschaltung", "Visible LED", "nach 5 Minuten"),
        "en": ("Emergency stop", "Visible LED", "after 5 minutes"),
        "es": ("Apagado de emergencia", "LED visible", "después de 5 minutos")
    },
    "focus_RPI_M3_1": {
        "sleep": 1,
        "de": ("Fokusschleife", "startet", ""),
        "en": ("Focusing loop", "starts", ""),
        "es": ("Bucle de enfoque", "comienza", "")
    },
    "focus_RPI_M3_2": {
        "sleep": 3,
        "de": ("Foksieren beendet", "Dioptrien alt: {dioptrien_alt}", "Dioptrien neu: {dioptrien_neu}"),
        "en": ("Focusing ended", "Diopters old: {dioptrien_alt}", "Diopters new: {dioptrien_neu}"),
        "es": ("Enfoque terminado", "Dioptrías antiguas: {dioptrien_alt}", "Dioptrías nuevas: {dioptrien_neu}")
    },
    ### rtc ###
    "rtc_1": {
        "sleep": 0,
        "de": ("Datum einstellen","{date}",""),
        "en": ("Set date","{date}",""),
        "es": ("Ajustar fecha","{date}","")
    },     
    "rtc_2": {
        "sleep": 0,
        "de": ("Zeit einstellen","{time}",""),
        "en": ("Set time","{time}",""),
        "es": ("Ajustar hora","{time}","")
    },  
    "rtc_3": {
        "sleep": 3,
        "de": ("ungültiges Jahr","neu eingeben",""),
        "en": ("Invalid year","try again",""),
        "es": ("Año inválido","ingresar de nuevo","")
    },  
    "rtc_4": {
        "sleep": 3,
        "de": ("ungültiger Monat", " neu eingeben",""),
        "en": ("Invalid month","try again",""),
        "es": ("Mes inválido","ingresar de nuevo","")
    },  
    "rtc_5": {
        "sleep": 3,
        "de": ("ungültiger Tag","neu eingeben",""),
        "en": ("Invalid day","try again",""),
        "es": ("Día inválido","ingresar de nuevo","")
    },
    "rtc_6": {
        "sleep": 3,
        "de": ("ungültige Stunde", "neu eingeben",""),
        "en": ("Invalid hour","try again",""),
        "es": ("Hora inválida","ingresar de nuevo","")
    },  
    "rtc_7": {
        "sleep": 3,
        "de": ("ungültige Minute", "neu eingeben",""),
        "en": ("Invalid minute","try again",""),
        "es": ("Minuto inválido","ingresar de nuevo","")
    },  
    "rtc_8": {
        "sleep": 3,
        "de": ("ungültige Sekunde", "neu eingeben",""),
        "en": ("Invalid second","try again",""),
        "es": ("Segundo inválido","ingresar de nuevo","")
    },  
    "rtc_9": {
        "sleep": 2,
        "de": ("Ungültige Eingabe!", "erneut versuchen",""),
        "en": ("Invalid input!","try again",""),
        "es": ("Entrada inválida!","intente de nuevo","")
    },  
    "rtc_10": {
        "sleep": 3,
        "de": ("Warnung: Nur","Raspberry Zeit","aktualisiert"),
        "en": ("Warning: Only","Raspberry time","updated"),
        "es": ("Advertencia: Solo","hora de Raspberry","actualizada")
    },
            
    ### camera ###
    "cam_1": {
        "sleep": 1,
        "de": ("Kamera Test","Kamera wird","initialisiert"),
        "en": ("Camera test","Camera is","initializing"),
        "es": ("Prueba de cámara","La cámara se","inicia")
    },    
    "cam_2": {
        "sleep": 2,
        "de": ("Kamera Test","Zugriff","erfolgreich"),
        "en": ("Camera test","Access","successful"),
        "es": ("Prueba de cámara","Acceso","exitoso")
    },   
    "cam_3": {
        "sleep": 2,
        "de": ("Kamera Test","Zugriff","gescheitert"),
        "en": ("Camera test","Access","failed"),
        "es": ("Prueba de cámara","Acceso","fallido")
    },   
    "cam_4": {
        "sleep": 0,
        "de": ("Kamera Test","Kamera wird", "eingeschaltet"),
        "en": ("Camera test","Camera is","powering on"),
        "es": ("Prueba de cámara","La cámara se","enciende")
    },   
    "cam_5": {
        "sleep": 1,
        "de": ("Dimme","UV Lampe","hoch"),
        "en": ("Dim","UV lamp","up"),
        "es": ("Aumentar","lámpara UV","")
    },   
    "cam_6": {
        "sleep": 1,
        "de": ("Dimme","UV Lampe","runter"),
        "en": ("Dim","UV lamp","down"),
        "es": ("Disminuir","lámpara UV","")
    },   
    "cam_7": {
        "sleep": 2,
        "de": ("Bild","gespeichert",""),
        "en": ("Image","saved",""),
        "es": ("Imagen","guardada","")
    },  
    
    "cam_UV": {
        "sleep": 3.5,
        "de": ("","UV",""),
        "en": ("","UV",""),
        "es": ("","UV","")
    }, 
    
    ### gps ###
    "gps_1": {
        "sleep": 2,
        "de": ("Bitte", "Hemisphären", "eingeben"),
        "en": ("Please", "enter hemisphere", ""),
        "es": ("Por favor", "ingrese hemisferio", "")
    }, 
    "gps_2": {
        "sleep": 0,
        "de": ("▲ = Nord", "", "▼ = Süd"),
        "en": ("▲ = North", "", "▼ = South"),
        "es": ("▲ = Norte", "", "▼ = Sur")
    }, 
    "gps_3": {
        "sleep": 0,
        "de": ("▲ = Ost", "", "▼ = West"),
        "en": ("▲ = East", "", "▼ = West"),
        "es": ("▲ = Este", "", "▼ = Oeste")
    }, 
    "gps_4": {
        "sleep": 0,
        "de": ("Breite (N-S):","{Breite}",""),
        "en": ("Latitude (N-S):","{Breite}",""),
        "es": ("Latitud (N-S):","{Breite}","")
    },
    "gps_5": {
        "sleep": 0,
        "de": ("Länge (O-W):","{Länge}",""),
        "en": ("Longitude (E-W):","{Länge}",""),
        "es": ("Longitud (E-O):","{Länge}","")
    },
    "gps_6": {
        "sleep": 1,
        "de": ("Ungültige Breite!", "Bitte gültigen", "Wert wählen"),
        "en": ("Invalid latitude!", "Please choose", "a valid value"),
        "es": ("Latitud inválida!", "Seleccione un", "valor válido")
    },
    "gps_7": {
        "sleep": 1,
        "de": ("Ungültige Länge!", "Bitte gültigen", "Wert wählen"),
        "en": ("Invalid longitude!", "Please choose", "a valid value"),
        "es": ("Longitud inválida!", "Seleccione un", "valor válido")
    },
    "gps_8": {
        "sleep": 0,
        "de": ("Koordinaten", "gespeichert", ""),
        "en": ("Coordinates", "saved", ""),
        "es": ("Coordenadas", "guardadas", "")
    },
    "gps_9": {
        "sleep": 3,
        "de": ("Ungültige", "Koordinaten!", "Bitte erneut eingeben"),
        "en": ("Invalid", "coordinates!", "Please re-enter"),
        "es": ("Coordenadas", "inválidas!", "Ingrese de nuevo")
    },                               

    ### location ### 
    "side_1": {
        "sleep": .0125,
        "de": ("Land wählen:", "{country}", "rechts = bestätigen"),
        "en": ("Select country:", "{country}", "right = confirm"),
        "es": ("Seleccionar país:", "{country}", "derecha = confirmar")
    },   
    "side_2": {
        "sleep": .0125,
        "de": ("Provinz wählen:", "{province}", "rechts = bestätigen"),
        "en": ("Select province:", "{province}", "right = confirm"),
        "es": ("Seleccionar provincia:", "{province}", "derecha = confirmar")
    },   
    "side_3": {
        "sleep": .0125,
        "de": ("Kreis wählen: {Kreis}", "1. rechts = bestätigen", "2. Enter = beeenden"),
        "en": ("Select district: {Kreis}", "1. right = confirm", "2. Enter = finish"),
        "es": ("Seleccionar distrito: {Kreis}", "1. derecha = confirmar", "2. Enter = finalizar")
    },   
    "side_4": {
        "sleep": 2,
        "de": ("Auswahl","abgeschlossen",""),
        "en": ("Selection","finished",""),
        "es": ("Selección","finalizada","")
    },   
    "side_5": {
        "sleep": 3,
        "de": ("{country}","{province}","{Kreiscode}"),
        "en": ("{country}","{province}","{Kreiscode}"),
        "es": ("{country}","{province}","{Kreiscode}")
    },                   

    ### wait ### 
    "wait_1": {
        "sleep": 1,
        "de": ("Beginne in","{hours}:{minutes}:{seconds}",""),
        "en": ("Starting in","{hours}:{minutes}:{seconds}",""),
        "es": ("Comienza en","{hours}:{minutes}:{seconds}","")
    },   

    ### service ###
    "service_1": {
        "sleep": 1,
        "de": ("Lösche USB Daten", "Bitte warten", "{zaehler} / {gesamtzahl}"),
        "en": ("Deleting USB data", "Please wait", "{zaehler} / {gesamtzahl}"),
        "es": ("Borrando datos USB", "Por favor espere", "{zaehler} / {gesamtzahl}")
    },  

    ### end ###
    "end_1": {
        "sleep": 1,
        "de": ("ARNI startet", "neu in", "{time} Sekunden"),
        "en": ("ARNI restarts", "in", "{time} seconds"),
        "es": ("ARNI se reinicia", "en", "{time} segundos")
    },        

    ### error ###
    "err_1": {
        "sleep": 3,
        "de": ("Fehler 1", "Kamera - Prüfe", "Kabelverbindung"),
        "en": ("Error 1", "Camera - Check", "cable connection"),
        "es": ("Error 1", "Cámara - Verifique", "conexión del cable")
    },  
    "err_1a": {
        "sleep": 0,
        "de": ("Kamera - Prüfe", "Kabelverbindung","{tries}/91"),
        "en": ("Camera - Check", "cable connection", "{tries}/91"),
        "es": ("Cámara - Verifique", "conexión del cable", "{tries}/91")
    },     
    "err_2": {
        "sleep": 3,
        "de": ("Fehler 2", "Kamera überfordert", "nicht initialisiert"),
        "en": ("Error 2", "Camera busy", "not initialized"),
        "es": ("Error 2", "Cámara saturada", "no inicializada")
    }, 
    "err_3": {
        "sleep": 3,
        "de": ("Fehler 3", "USB Stick - Prüfe", "Anschluss"),
        "en": ("Error 3", "USB stick - Check", "connection"),
        "es": ("Error 3", "USB - Verifique", "conexión")
    },
    "err_4": {
        "sleep": 3,
        "de": ("Fehler 4", "Lichtsensor - Prüfe", "Sensorkabel"),
        "en": ("Error 4", "Light sensor - Check", "sensor cable"),
        "es": ("Error 4", "Sensor de luz - Verifique", "cable del sensor")
    }, 
    "err_5": {
        "sleep": 3,
        "de": ("Fehler 5", "Außensensor - Prüfe", "Sensorkabel"),
        "en": ("Error 5", "Outdoor sensor - ", "Check sensor cable"),
        "es": ("Error 5", "Sensor exterior - ", "Verifique cable")
    }, 
    "err_6": {
        "sleep": 3,
        "de": ("Fehler 6", "Innensensor", "Platinenfehler"),
        "en": ("Error 6", "Inner sensor", "board error"),
        "es": ("Error 6", "Sensor interior", "error de placa")
    }, 
    "err_7": {
        "sleep": 3,
        "de": ("Fehler 7", "Stromsensor", "Platinenfehler"),
        "en": ("Error 7", "Current sensor", "board error"),
        "es": ("Error 7", "Sensor de corriente", "error de placa")
    },                             
    "err_8": {
        "sleep": 3,
        "de": ("Fehler 8", "Hardware Uhr", "nicht gefunden"),
        "en": ("Error 8", "Hardware clock", "not found"),
        "es": ("Error 8", "Reloj de hardware", "no encontrado")
    },   
    "err_9": {
        "sleep": 3,
        "de": ("Fehler 9", "FRam", "Platinenfehler"),
        "en": ("Error 9", "FRam", "board error"),
        "es": ("Error 9", "FRam", "error de placa")
    }, 
    "err_10": {
        "sleep": 3,
        "de": ("Fehler 10", "Logging", "Prüfe USB"),
        "en": ("Error 10", "Logging", "Check USB"),
        "es": ("Error 10", "registro", "Verifique USB")
    }, 
    "err_11": {
        "sleep": 3,
        "de": ("Fehler 11", "Checksumme nicht", "ermittelt"),
        "en": ("Error 11", "Checksum not", "calculated"),
        "es": ("Error 11", "suma de verificación", "no calculada")
    }, 
    "err_12": {
        "sleep": 3,
        "de": ("Fehler 12", "Beleuchtungs LED", "verdunkelt"),
        "en": ("Error 12", "Visible LED", "darkened"),
        "es": ("Error 12", "Iluminación LED", "atenuada")
    }, 
    "err_13": {
        "sleep": 3,
        "de": ("Fehler 13", "Metadaten Tabelle", "Software/ USB Fehler"),
        "en": ("Error 13", "Metadata table", "Software/ USB error"),
        "es": ("Error 13", "Tabla de metadatos", "Error de software/ USB")
    }, 
    "err_14": {
        "sleep": 3,
        "de": ("Fehler 14", "Sanity Check","Foto unvollständig"),
        "en": ("Error 14", "Sanity Check","Photo incomplete"),
        "es": ("Error 14", "Sanity Check","Foto incompleta")
    },     
    "err_15": {
        "sleep": 3,
        "de": ("Fehler 15", "Paket Installation","fehlgeschlagen"),
        "en": ("Error 15", "Package installation","failed"),
        "es": ("Error 15", "Instalación de paquetes","fallida")
    },
    "err_16": {
        "sleep": 3,
        "de": ("Fehler 16", "Land/ Region","nicht bestimmt"),
        "en": ("Error 16", "Country/ Region","not determined"),
        "es": ("Error 16", "País/ Región","no determinado")
    },
                            
    ### blank ###
    "blank": {
        "sleep": 1,
        "de": ("","",""),
        "en": ("","",""),
        "es": ("","","")
    }
}    



def show_message_register(start_key=None, lang="de", dummy_values=None):
    """
    Zeigt alle Nachrichten aus dem MESSAGE_REGISTER nacheinander auf dem OLED an.
    Startpunkt kann per Schlüsselname gesetzt werden. Platzhalter werden mit Dummy-Werten ersetzt.
    :param start_key: Schlüsselname, ab dem gestartet wird (inklusive)
    :param lang: Sprache ('de', 'en', 'es', ...)
    :param dummy_values: Dict mit Dummy-Werten für Platzhalter
    """
    from OLED_panel import show_message
    keys = list(MESSAGE_REGISTER.keys())
    if start_key is not None:
        try:
            start_idx = keys.index(start_key)
        except ValueError:
            print(f"Startschlüssel '{start_key}' nicht gefunden. Starte bei erstem Eintrag.")
            start_idx = 0
    else:
        start_idx = 0

    if dummy_values is None:
        dummy_values = {
            "hardware": "HW1",
            "sn": "123456",
            "version": "1.0.0",
            "date": "01.01.2026",
            "time": "12:00",
            "provinz": "TestProvinz",
            "Kreiscode": "000",
            "latitude": "50.0N",
            "longitude": "8.0E",
            "country_name": "Deutschland",
            "region_name": "Hessen",
            "package": "testpkg",
            "Exposure": "100",
            "Gain": "1.0",
            "average_brightness": "128",
            "variance_old": "10",
            "variance_new": "12",
            "dioptrien_alt": "1.0",
            "dioptrien_neu": "1.5",
            "Breite": "50.0N",
            "Länge": "8.0E",
            "country": "Deutschland",
            "province": "Hessen",
            "Kreis": "TestKreis",
            "total_space": "32",
            "free_space": "16",
            "sunset": "18:00",
            "sunrise": "06:00",
            "hours": "01",
            "minutes": "00",
            "seconds": "00",
            "zaehler": "1",
            "gesamtzahl": "10",
            "tries": "1",
        }

    for key in keys[start_idx:]:
        entry = MESSAGE_REGISTER[key]
        # Platzhalter mit Dummy-Werten füllen, falls nötig
        try:
            show_message(key, lang, **dummy_values)
            time.sleep(3)
            print(f"Angezeigte Nachricht: '{key}' in Sprache '{lang}'")
        except Exception as e:
            print(f"Fehler bei Nachricht '{key}': {e}")



if __name__ == "__main__":
    '''
    print("alle Nachrichten des Registers")
    print("-------------------------------------------------------\n")
    # test print all messages
    for key in MESSAGE_REGISTER:
        print(f"Message ID: {key}")
        print(" German:")
        for line in MESSAGE_REGISTER[key]["de"]:
            print(f"  {line}")
        print(" English:")
        for line in MESSAGE_REGISTER[key]["en"]:
            print(f"  {line}")
        print(" Spanish:")
        for line in MESSAGE_REGISTER[key]["es"]:
            print(f"  {line}")
        print("\n")
    '''
    print("Gebe Start Key zur Anzeige auf OLED ein")
    start_key = str(input())
    print("-------------------------------------------------------\n")
    print("-------------------------------------------------------\n")
    print("-------------------------------------------------------\n")

    show_message_register(start_key=start_key, lang="en")