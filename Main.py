from start_up import *
from trap_hmi import *
from capturing import *
from end import *
from package_whl_installer import install_packages
from capturing_state import reset_state
from logging_utils import log_schreiben


if __name__ == "__main__":

    # The web service is owned by the lepmon-web.service systemd unit
    # (always-on, independent of this process). reset_state() runs *after*
    # so any focus flags the web service set are reset cleanly.
    reset_state()

    try:
        start_up("log")
    except Exception as e:
        print(f"Fehler im Start-Up: {e}", "log")

    #install_packages("log")

    try:
        open_trap_hmi("log")
    except Exception as e:
        try:
            log_schreiben(f"Fehler im HMI: {e}", "log")
        except Exception as log_error:
            print(f"Fehler im HMI: {e}", "log")

    try:
        capturing("log")
    except Exception as e:
        try:
            log_schreiben(f"Fehler im Capturing: {e}", "log")
        except Exception as log_error:
            print(f"Fehler im Capturing: {e}", "log")
    
    try:
        trap_shutdown(i=60, log_mode="log", execution="full")
    except Exception as e:
        try:
            log_schreiben(f"Fehler im Shutdown: {e}", "log")
        except Exception as log_error:
            print(f"Fehler im Shutdown: {e}", "log")

    print("Programmende erreicht.")
    print("..." )