from start_up import *
from trap_hmi import *
from capturing import *
from end import *
from package_whl_installer import install_packages
from capturing_state import reset_state
from logging_utils import log_schreiben

# Start the web service in background
def start_web_service():
    """Start the FastAPI web service in a background thread."""
    try:
        from lepmon_web_service import start_background_server
        start_background_server(host="0.0.0.0", port=8080)
        print("Lepmon Web Service started on http://0.0.0.0:8080")
    except Exception as e:
        print(f"Warning: Could not start web service: {e}")

        

if __name__ == "__main__":
    
    reset_state()
    
    # Start web service first (runs in background)
    start_web_service()
    
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