from logging_utils import *
from fram_direct import *
from times import *


log_mode = "manual"

experiment_start_time, experiment_end_time, _, _ = get_experiment_times()
try:
        estimated_start_based_on_last_run = read_fram(0x06A0,19)

        print(estimated_start_based_on_last_run)

        estimated_end_based_on_last_run = read_fram(0x06C0,19)
        estimated_start_based_on_last_run = datetime.strptime(estimated_start_based_on_last_run, "%Y-%m-%d %H:%M:%S")
        estimated_end_based_on_last_run = datetime.strptime(estimated_end_based_on_last_run, "%Y-%m-%d %H:%M:%S")
        print(estimated_start_based_on_last_run, estimated_end_based_on_last_run)

except Exception as e:
        log_schreiben(f"Fehler beim lesen der zuletzt in 'end' gespeicherten Zeiten:{e}", log_mode=log_mode)
        log_schreiben(f"Vergleiche Experiment Zeiten", log_mode=log_mode)
        log_schreiben("----------------------------------------------", log_mode=log_mode)
        log_schreiben(f"{'gespeicherter Anfang':<22} | {estimated_start_based_on_last_run}", log_mode=log_mode)
        log_schreiben(f"{'gespeichertes Ende':<22} | {estimated_end_based_on_last_run}", log_mode=log_mode)

try: 
        experiment_start_time = datetime.strptime(experiment_start_time.strip(), "%H:%M:%S")
        #experiment_start_time = datetime.now().time()
        diff_start = estimated_start_based_on_last_run - experiment_start_time
        log_schreiben(f"{'Differenz in Startzeiten':<22} | {diff_start}", log_mode=log_mode)
except Exception as e:
        log_schreiben(f"Fehler im Vergleich der Startzeit aus 'end' und der tatsächlichen Startzeit:{e}", log_mode=log_mode)
        