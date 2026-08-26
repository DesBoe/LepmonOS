from times import *
from json_read_write import *
from logging_utils import *
import json
from datetime import datetime
try:
    import pandas as pd
except Exception as e:
    print(e)

CONFIG_PATH = "/home/Ento/LepmonOS/Lepmon_config.json"
Enable_Delay = get_value_from_section(CONFIG_PATH, "Experiment_Delay", "Enable_Delay")
Enable_Interval = get_value_from_section(CONFIG_PATH, "Experiment_Interval", "Enable_Interval")
ARNIS_Delay_Experiment = []
ARNIs_Interval_Experiment = []

def get_section(CONFIG_PATH, section_name):
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get(section_name, {})

def get_arni_values(CONFIG_PATH, section_name):
    section = get_section(CONFIG_PATH, section_name)

    # Alle Keys wie "Test-ARNI-1", "Test-ARNI-2", ...
    arni_keys = [k for k in section.keys() if "ARNI" in k]

    values = []
    for key in arni_keys:
        v = get_value_from_section(CONFIG_PATH, section_name, key)
        if v is not None:
            values.append(v)

    return values


if get_value_from_section(CONFIG_PATH, "Experiment_Delay", "Enable_Delay"):
    ARNIS_Delay_Experiment = get_arni_values(CONFIG_PATH, "Experiment_Delay")

if get_value_from_section(CONFIG_PATH, "Experiment_Interval", "Enable_Interval"):
    ARNIs_Interval_Experiment = get_arni_values(CONFIG_PATH, "Experiment_Interval")



def write_experiment_overview_in_start_up(sn, experiment_start_time, log_mode):

    print("Prüfe ARNI auf Teilnahme im Experiment für Boundingboxen mit Delay")
    if sn in ARNIS_Delay_Experiment and Enable_Delay:
        jetzt_local, _, _= Zeit_aktualisieren(log_mode=log_mode)
        Delay, Box_Experiment_Run, Round = get_experiment_delay(sn, jetzt_local)
        Delay_str = str(Delay).split()[-1]
        log_schreiben("==============================================", log_mode=log_mode)
        log_schreiben(f"ARNI im Experiment für Boundingboxen mit Delay eingesetzt", log_mode=log_mode)
        log_schreiben("----------------------------------------------", log_mode=log_mode)
        log_schreiben(f"{'Verzögerung':<22} | {Delay_str}", log_mode=log_mode)
        log_schreiben(f"{'Box Experiment Run':<22} | {Box_Experiment_Run}", log_mode=log_mode)
        log_schreiben(f"{'Runde':<22} | {Round}", log_mode=log_mode)
        log_schreiben("==============================================", log_mode=log_mode)
        try:
            log_schreiben(f"Start auf diesem ARNI: {experiment_start_time + Delay}", log_mode=log_mode)
        except Exception as e:
            log_schreiben(f"Fehler beim Berechnen der Startzeit mit Delay: {e}", log_mode=log_mode)


    print("Prüfe ARNI auf Teilnahme im Experiment für Interval")
    log_schreiben("==============================================", log_mode=log_mode)
    if sn in ARNIs_Interval_Experiment and Enable_Interval:
        interval_for_experiment = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "Experiment_Interval", "interval_for_experiment")
        Skip_Sanity_Check = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "Experiment_Interval", "Skip_Sanity_Check")
        log_schreiben(f"ARNI im Experiment für Intervalle eingesetzt", log_mode=log_mode)
        log_schreiben("----------------------------------------------", log_mode=log_mode)
        log_schreiben(f"{'Intervall':<22} | {interval_for_experiment} Minuten", log_mode=log_mode)
        log_schreiben(f"{'Skip Sanity Check':<22} | {Skip_Sanity_Check}", log_mode=log_mode)
        
    elif not sn in ARNIs_Interval_Experiment or not Enable_Interval:
        interval = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "capture_mode", "interval")
        log_schreiben(f"{'Intervall':<22} | {interval} Minuten", log_mode=log_mode)
    log_schreiben("==============================================", log_mode=log_mode)



def load_experiment_table(csv_path):
    df = pd.read_csv(csv_path)

    # Zeitspalten konvertieren
    df["Start"] = pd.to_datetime(df["Start"], format="%d.%m.%y %H:%M")
    df["End"] = pd.to_datetime(df["End"], format="%d.%m.%y %H:%M")

    # Delay als timedelta (Minuten)
    df["Delay_timedelta"] = pd.to_timedelta(df["Delay"], unit="m")

    return df


def get_experiment_delay(sn, timestamp):
    """
    sn: z.B. "SN010010"
    timestamp: datetime oder String
    """

    try:
        df = load_experiment_table("/home/Ento/LepmonOS/Box_Experiment_Delays.csv")
    except:
        try:
            df = load_experiment_table("/Volumes/Dennis_OTG/LEPMON/Raspberry_Pi/LepmonOS/Experiment_Box_Delays.csv")
        except Exception as e:
            print(f"Fehler beim Laden der Experimenttabelle: {e}")
    # Falls String → datetime
    timestamp = pd.to_datetime(timestamp)

    # Filter: richtige SN + Zeit liegt im Intervall
    mask = (
        (df["SN"] == sn) &
        (df["Start"] <= timestamp) &
        (df["End"] > timestamp)
    )

    result = df.loc[mask]

    if result.empty:
        return None  # nichts gefunden

    row = result.iloc[0]

    
    Delay= row["Delay_timedelta"]
    Box_Experiment_Run = row["Box_Experiment_Run"]
    Round = row["Round"]

    return Delay, Box_Experiment_Run, Round



def apply_delay(experiment_start_time, log_mode):
            sn = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","general","serielnumber")  
            if sn in ARNIS_Delay_Experiment and Enable_Delay:    
                jetzt_local, _, _= Zeit_aktualisieren(log_mode=log_mode)
                Delay, Box_Experiment_Run, Round = get_experiment_delay(sn, jetzt_local)
                print(f"Delay für diesen ARNI in dieser Nacht:{Delay}")
                experiment_start_time += Delay

            return experiment_start_time

def get_interval(log_mode):
    interval = 2
    sn = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","general","serielnumber")  
    sn = "SN010010"
    if sn in ARNIs_Interval_Experiment and Enable_Interval:
        interval = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "Experiment_Interval", "interval_for_experiment")
        print(f"Interval für Experiment wird angewendet: {interval} Min auf ARNI {sn}")
    elif not sn in ARNIs_Interval_Experiment or not Enable_Interval:
        interval = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "capture_mode", "interval")
        print(f"Interval für normalen Betrieb wird angewendet: {interval} Min auf ARNI {sn}")

    return interval

    
          
     




if __name__ == "__main__":
    sn = "SN010010"
    log_mode = "manual"
    now = datetime.now()
    zeit = now.strftime("%H:%M:%S") 
    print("----------")
    write_experiment_overview_in_start_up(sn, zeit, log_mode)
    print("----------")
    apply_delay(zeit)
    print("----------")
    get_interval(log_mode)





    