import csv
from datetime import datetime, timedelta

csv_path = "Box_Experiment_Delays.csv"
sn_list = ["SN010010", "SN010011"]
delay_pattern = [0, 30, 60, 90, 120]

# Finde das letzte Datum, Run-Index und Round in der bestehenden Datei
last_date = None
last_run = 0
last_round = 1
with open(csv_path, newline='') as csvfile:
    reader = csv.reader(csvfile)
    next(reader)  # Header überspringen
    for row in reader:
        if len(row) >= 4 and row[0] and row[2].startswith("Box_Experiment_Run_"):
            d = datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S")
            run = int(row[2].split("_")[-1])
            rnd = int(row[3])
            if last_date is None or d > last_date:
                last_date = d
                last_run = run
                last_round = rnd

# Startdatum für neue Einträge
if last_date is None:
    last_date = datetime(2026, 4, 1, 12, 0, 0)
    last_run = 1
    last_round = 1
else:
    last_date += timedelta(days=1)
    last_run += 1

end_date = datetime(2026, 12, 30, 12, 0, 0)

rows = []
current_date = last_date
run = last_run
round_ = last_round

# Delay-Index für jede SN und Runde getrennt führen
delay_idx_10 = 0
delay_idx_11 = 0

while current_date <= end_date:
    # alle 5 Runs neue Runde
    if (run - 1) % 5 == 0 and run != last_run:
        round_ += 1
        # Delay-Index für jede Runde zurücksetzen
        delay_idx_10 = 0
        delay_idx_11 = 0
    next_date = current_date + timedelta(days=1)
    for sn in sn_list:
        if round_ % 2 == 1:  # ungerade Runde: SN11 immer 0, SN10 bekommt Pattern
            if sn == "SN010010":
                delay = delay_pattern[delay_idx_10 % len(delay_pattern)]
                delay_idx_10 += 1
            else:
                delay = 0
        else:  # gerade Runde: SN10 immer 0, SN11 bekommt Pattern
            if sn == "SN010011":
                delay = delay_pattern[delay_idx_11 % len(delay_pattern)]
                delay_idx_11 += 1
            else:
                delay = 0
        rows.append([
            current_date.strftime("%Y-%m-%d %H:%M:%S"),
            next_date.strftime("%Y-%m-%d %H:%M:%S"),
            f"Box_Experiment_Run_{run:03d}",
            round_,
            sn,
            delay
        ])
    current_date = next_date
    run += 1

# Schreibe die neuen Zeilen ans Ende der Datei
with open(csv_path, "a", newline='') as csvfile:
    writer = csv.writer(csvfile)
    for row in rows:
        writer.writerow(row)

print(f"Fertig! Ergänzt bis {end_date.strftime('%Y-%m-%d')}.")