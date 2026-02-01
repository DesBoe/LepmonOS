from start_up import *
from trap_hmi import *
from capturing import *
from end import *
from package_whl_installer import install_packages
from capturing_state import reset_state

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
    # Reset capture state on startup
    reset_state()
    
    # Start web service first (runs in background)
    start_web_service()
    
    start_up("log")
    install_packages("log")
    open_trap_hmi("log")
    capturing("log")
    trap_shutdown("log",60)