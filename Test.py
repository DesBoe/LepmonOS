
import hashlib



def checksum(dateipfad, log_mode, algorithm="md5"):
  try:
    if not os.path.exists(dateipfad): 
        raise FileNotFoundError(f"Datei nicht gefunden: {dateipfad}")
    hash_func = hashlib.new(algorithm) 
    
    with open(dateipfad, "rb") as file:
        while chunk := file.read(8192):
            hash_func.update(chunk)
 
    checksum = hash_func.hexdigest()
  
    dir_name = os.path.dirname(dateipfad)
    base_name = os.path.basename(dateipfad)
    checksum_file_name = f"{base_name}.{algorithm}"
    checksum_dateipfad = os.path.join(dir_name, checksum_file_name)
  
    with open(checksum_dateipfad, "w") as checksum_file:
      checksum_file.write(checksum)
  
  except Exception as e:
    error_message(11,e, log_mode)
    print(f"Fehler beim Berechnen der Prüfsumme: {e}")
    pass
 
def checklist(dateipfad, log_mode, algorithm="md5"):
    try:
        log_path = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "general", "current_log")
        base, _ = os.path.splitext(log_path)
        checklist_path = f"{base}_MD5.txt"
        
        if os.path.abspath(dateipfad) == os.path.abspath(checklist_path):
            return
        
        if not dateipfad.isascii():
                    normalized = unicodedata.normalize('NFKD', dateipfad).encode('ascii', errors='ignore').decode('ascii').strip()
                    if normalized and os.path.splitext(normalized)[1]:
                        log_schreiben(f"Warnung: Dateipfad enthielt non-ASCII-Zeichen, bereinigt: {dateipfad!r} → {normalized!r}", log_mode=log_mode)
                        dateipfad = normalized
                    else:
                        log_schreiben(f"Warnung: Dateipfad enthält ungültige Zeichen (non-ASCII): {dateipfad!r}", log_mode=log_mode)
                        raise ValueError(f"Ungültiger Dateipfad (enthält non-ASCII-Zeichen): {dateipfad!r}")

                        #TODO Peter und Christian müssen entscheiden, wie es in so einem Fall weiter gehen soll

        if not os.path.exists(dateipfad):
            raise FileNotFoundError(f"Datei nicht gefunden: {dateipfad}")

        # Checksumme berechnen
        hash_func = hashlib.new(algorithm)
        with open(dateipfad, "rb") as file:
            while chunk := file.read(8192):
                hash_func.update(chunk)
        checksum_value = hash_func.hexdigest()
        base_name = os.path.basename(dateipfad)
        entry = f"{checksum_value} {base_name}\n"

        # Prüfe, ob checklist.txt existiert, sonst anlegen
        if not os.path.exists(checklist_path):
            with open(checklist_path, "w", encoding="utf-8") as f:
                f.write(entry)
            return

        # Für csv/log: Eintrag ersetzen, für Bilder: ergänzen
        update_entry = base_name.endswith(".csv") or base_name.endswith(".log")
        lines = []
        found = False

        import re
        _valid_line = re.compile(r'^[0-9a-fA-F]+\s+\S+\s*$')

        with open(checklist_path, "r", encoding="utf-8", errors="replace") as f:
            raw_lines = f.readlines()

        # Korrumpierte Zeilen herausfiltern (enthalten Ersetzungszeichen oder passen nicht zum Format)
        for line in raw_lines:
            if '\ufffd' in line or not _valid_line.match(line.rstrip('\n')):
                print(f"Korrumpierte Zeile in Checklist übersprungen: {line[:60]!r}")
                continue
            lines.append(line)

        if update_entry:
            for i, line in enumerate(lines):
                if line.strip().split()[-1] == base_name if line.strip().split() else False:
                    lines[i] = entry
                    found = True
                    break
            if not found:
                lines.append(entry)
        else:
            lines.append(entry)

        with open(checklist_path, "w", encoding="utf-8") as f:
            f.writelines(lines)

    except Exception as e:
        print(f"Fehler beim Berechnen der Checkliste: {e}")
        pass 
 
if __name__ == "__main__":
    print("logging Werkzeuge")

    checklist("Lepmon#SN010149/µ∫Ñª∏È∫∆7•«*1Àt” ¸ï67«ÊBmÜ$N≈Å§ìæ€ l$3¶", "manual", algorithm="md5")