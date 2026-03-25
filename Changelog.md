# Changelog


## [2.3.1] 2026-03-25
### Geändert
- Fehlertolleranz für schwarze Pixel auf 15% angehoben
- Referenzwert für gut belichtete Bilder: 185 (Toleranz: ±5, vorher 170 ±8)

### Hinzugefügt
- Weißabgleich in der ersten Nacht nach Nutzereingabe, sobald ein gut belichtetes Bild aufgenommen wurde
- Maximale Zeit für Wartedauer zwischen 2 Aufnahmen ist Intervall

### Behoben
- Problem beim messen und schreiben beim Verbrauch der visible LED


## [2.3.0] 2026-03-17
### Geändert
- Installation via SD Karten image
- Start der Aufnahme pauschal 10 Minuten nach Sonnenuntergang
- VimbaX statt Vimba
- SD-Image: LepmonOS_Dev_* und LepmonOS_Service_* Dateien werden nicht mehr im Image ausgeliefert
- SD-Image wird nach dem Build verkleinert (shrink), um unter 2 GB GitHub-Release-Limit zu bleiben
- Journald Log-Speicher auf 16 MB begrenzt
- Build-Essential und unnötige Firmware nach Installation entfernt (Platzersparnis)
- Release-Notes in GitHub Actions aktualisiert
- move Photo Sanity check in snap image function for shorter time between 2 consequtive frames

### Hinzugefügt
- detailierte Fehler Logs in der Alied Vision Kamera
- Leichtgewichtiger LXDE-Desktop vorinstalliert, aktivierbar via `lepmon-desktop on` (CLI bleibt Standard)
- SSH robust aktiviert: ConditionPathExists entfernt, PasswordAuthentication und PermitRootLogin aktiviert
- I2C über raspi-config und zusätzliches Kernel-Modul `i2c-bcm2835` sichergestellt
- Boot-Login-Problem behoben: getty@tty1 und serial-getty werden explizit aktiviert/unmasked; cmdline.txt ergänzt
- Bildergalerie im Web-Frontend: Die letzten 10 aufgenommenen Bilder vom USB-Stick werden angezeigt
- API-Endpunkte `/api/images/latest`, `/api/images/file`, `/api/images/thumbnail` für Bildergalerie
- Lightbox-Ansicht für Vollbild-Betrachtung der aufgenommenen Bilder
- Automatische Galerie-Aktualisierung alle 60 Sekunden
- Convenience-Script `lepmon-desktop` zur Desktop-Verwaltung
- Disk-Cleanup: man-pages, docs, locale, __pycache__, pip-cache, unnötige Firmware entfernt

### Behoben
- Problem, dass ARNI keine Bilder aufnimmt
- SSH war nicht standardmäßig aktiviert über WiFi und Ethernet Verbindungen
- Boot blieb bei systemd-update-utmp-runlevel hängen, bevor Login-Prompt erschien
- I2C Aktivierung über zusätzliches Kernel-Modul und raspi-config abgesichert


## [2.2.0] 2026-03-02
### Geändert
- Visible nur bei Befehl der Frame erstellung an
- Strom Sensor nur 1x initialisiert, nicht bei jedem Lesen
- Anzeige während des Neustart
- Neuer Ansatz zur Berechnung der Sonnenzeiten
- Positionszeiger bei Uhrzeit und Koordianten nur noch ein "x", führende Striche entfallen
- Heizung nur zu Beginn der Aufnahme aktiv, nicht zu der Beginn der Funktion Wait, wenn die heizung ausgewählt wird
- Korrekturfaktor des Stromsensors auf 0.00494 angepasst
- LEMPNON Code nur aus ASCII Zeichen: Kreise mit Ä Ö Ü sollen auf A O U umgestellt werden. ARNI fordert die Nutzer dazu auf.
- ARNI passt die Belichtungszeit und den Gain der Kamera automatisch an, um Belichtungskorrekturen vorzunehmen
- Bei einer Unterbrechung der Aufnahmeschleife werden die Bilder nach erneutem Start in dem alten Ordner dieser Nacht abgelegt. Das Logfile erstellt einen Eintrag.
- Bei Änderung des Lepmon codes wird dieser nach der Diagnose angewendet. Der Ordner und Log werden umbenannt, kein neuer Ordner, kein Neustart
- Fokussierhilfe ermittelt Belichtung selbst und gibt Feedback, in welche Richtung fokusiert werden soll

### Hinzugefügt
- dimmer pwm auf 100 bei Vis
- message Library für Display Anzeigen
- Menü auf Englisch und Spanisch verfügbar
- SD Karten austauschbar: Generationen label wird zusätzlich zur SN in die separate JSON Datei geschrieben
- Sanity Check für aufgenommene Fotos. Graukonvertierung und Anteil Schwarzer Pixel wird berechnet
- Fehler 12 Visible LED verdunkelt und 7 Stromsensor aus Anzeige und Häufigkeitszählung entfernt
- logfile mit Nummer des Geräte Laufes
- Zeitstempel der letzten Raspberry Aktivität im FRam
- immer zur jeden zweiten vollen Stunde in der Aufnahme Schleife wird der USB Stick neu gemounted, um eine Assynchronität im Bus zu vermeiden.
- Gamma Korrektur der aufgenommenen Frames, um Schatten aufzuhellen (Schrittweise, je 1/3 des Frames gleichzeitig)
- Daylight Saving: Uhrumstellung im Frühjahr und Herbst
- im HMI kann für eine Korrektur bei der Eingabe mit der Taste "Rechts" zurückgegangen werden
- Nach der GPS Koordinaten Eingabe ermittelt ARNI das Land und die Provinz, in der die eingegebenen Koordinaten liegen. Der Nutzer muss dies bestätigen oder die Koordinaten neu eingeben. Diese Angaben haben keine Auswirkungen auf den LEPMON-Code
- Unterstützung für Raspberry "Pi HQ Camera" und "Raspberry Pi Camera Module 3"

### Behoben
- Fehler 3 wird bei gezogenem USB Stick während der Aufnahme Schleife angezeigt

## [2.1.1] 2025-09-11
### Geändert
- Begriff "Falle" aus Log Datei, CSV und Anzeigen entfernt und durch "ARNI" ersetzt

### Hinzugefügt
-

### Behoben
- Kreiskürzel, die Umlaute (Ä,Ö, oder Ü) haben und ingsamt 3 Buchstaben umfassen können nun vollständig ausgelesen werden


## [2.1.0] - 2025-09-05
### Geändert
- Zeitverzögertes Auslesen der Sensoren vor Aufnahme des Bildes
- Wenn der Lepmon Code geändert wird und im nächsten Anschalten der USB Stick gelöscht wird, wird der ordner mit dem Eintrag der Code Änderung nicht gelöscht.
- Dimmer Pin auf High während Bildaufnahme, um Flackern zu vermeiden
- Sonnen aufgang für loakle Zeitzone

### Hinzugefügt
- Innensensor und Stromsensor Kompatibel zu Pro_Gen_1
- Auslesen des Generationen Labels
- Fehler 9 wird in Pro_Gen_1 und Pro_Gen_2 nicht mehr angezeigt (kein Ram Modul verbaut)
- Art der Stromversorgung im CSV Kopf
- "Stadt" in "Kreis" umbenannt
- Kreise nach der der Referenz des ADAC: https://www.adac.de/rund-ums-fahrzeug/auto-kaufen-verkaufen/kfz-zulassung/kfz-kennzeichen-deutschland/
- Nutzer können im Menü die Heizung anschalten. Wird diese Option gewählt, ist die Scheibenheizung zu Beginn der Wartschleife und/oder während der ersten 8 Aufnahmen aktiv
- Kamera Schaltbar mit separatem USB-Y- Kabel
- eintag in boot/firmware/config.txt, um beim Start die spot LED zu unterdrücken

### Behoben
-Named Pipes und Sockets werden beim Update Prozess übersprungen


## [2.0.10] - 2025-07-23
### Geändert
- Kamerapin 28 --> 29 in GPIO Setup
- USB path Funktion um search counter erhöht
- aktivieren UV LED bei Kamera Test
- Kamera Funktion
- Logik der Wait Funktion angepasst, um Neustart bei Experimentbeginn zu vermeiden
- checksummen für .csv und .log Dateien direkt in log und csv Funktion integriert, neues modul check_sum
- Neue Formel für Sonnen- und Mondzeiten
- print befehle der fram read write funktionen
- Lepmon Code in GPS Funktion
- zu frühes drücken von enter in site selection führt nicht mehr zum abbruch
- neue focus Funktion
- Power off time für Attiny geändert in Funktion: Sonnenaufgang - 55 minuten
- Logik im Endskript. Fehler 10-13 führen trotzdem zu einem normalen Ende
- alle RAM Operationen sind mit try except abgefangen, um Abwärtskompatibilität zu gewährleisten

### Hinzugefügt
- trap_shutdown(3) in trap_hmi
- Stadtcode R und MR
- Fallen ID im Logfile
- USB Stick löschen
- Koordinaten im Logfile nach lokalem HMI 
- runtime fibt delay aus, um 2 Neustarts binnen 1 Minute zu verzögern
- Update Ordner wird nach update auf USB Stick gelöscht
- leerzeichen bei geprintetedn Lora messages
- Lepmoncode auch in RAM
- GPS im RAM, überschreibt Koordinaten im json file --> Nutzer müssen bei künftigen Updates diese Daten nicht neu eingeben
- Lepmon Code im Ram, überschreibt json file -> Nutzer müssen bei künftigen Updates diese Daten nicht neu eingeben

### Behoben
- ordner initialisierung in start_up.py
- nur Eintrag, wenn Uhrzeit nicht aktualisert wurde
- wait funktion ohne -60 Sekunden am Ende

## [2.0.9] - 2025-06-10
### Initial
- 1. Softwareversion 2.0.9 veröffentlicht