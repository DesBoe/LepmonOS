import pandas as pd

def load_experiment_table(csv_path):
    df = pd.read_csv(csv_path)

    # Zeitspalten konvertieren
    df["Start"] = pd.to_datetime(df["Start"], format="%d.%m.%y %H:%M")
    df["End"] = pd.to_datetime(df["End"], format="%d.%m.%y %H:%M")

    # Delay als timedelta (Minuten)
    df["Delay_timedelta"] = pd.to_timedelta(df["Delay"], unit="m")

    return df


def get_experiment_delay(df, sn, timestamp):
    """
    sn: z.B. "SN010010"
    timestamp: datetime oder String
    """

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

    
    Delay= row["Delay_timedelta"],
    Box_Experiment_Run = row["Box_Experiment_Run"]
    Round = row["Round"]

    return Delay, Box_Experiment_Run, Round






df = load_experiment_table("/Volumes/Dennis_OTG/LEPMON/Raspberry_Pi/LepmonOS/Box_Experiment_Delays.csv")

Delay, Box_Experiment_Run, Round = get_experiment_delay(df, "SN010010", "2026-04-03 13:00")

print(Delay, Box_Experiment_Run, Round)