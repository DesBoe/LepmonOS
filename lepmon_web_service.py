#!/usr/bin/env python3
"""
Lepmon Web Service - FastAPI background service for camera streaming and monitoring.

This service provides:
- MJPEG streaming from Allied Vision camera with min/max stretch
- Web UI for monitoring and focus assistance
- Status API for system monitoring

The camera stream is only active when the main capturing loop is NOT running.
"""

import asyncio
import threading
import time
import cv2
import numpy as np
from urllib.parse import quote as urlquote
from fastapi import FastAPI, Response, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
import uvicorn
import os
import sys
import json
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Optional, Generator, List
import logging
import glob
from json_read_write import get_value_from_section, write_value_to_section
# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import capturing state module
from capturing_state import (
    get_capturing_state,
    CaptureState,
    is_stop_focus_requested,
    request_stop_focus,
)

# Thumbnail helpers shared with the capture loop.
from thumbnail_utils import (
    THUMBS_DIR_NAME,
    THUMB_MAX_PX,
    find_usb_mount as _find_usb_mount_shared,
    thumb_path_for as _thumb_path_for,
    make_thumbnail_bytes as _make_thumbnail,
    write_thumbnail_for,
    is_usb_path,
)

from dev_mode import DEV_MODE, note_mock
from mock_hardware import generate_mock_frame

# Global variables for camera management
camera_lock = threading.Lock()
current_frame: Optional[np.ndarray] = None
frame_available = threading.Event()
streaming_active = False
stream_consumers = 0
stream_consumers_lock = threading.Lock()
dimming_active = False
dimming_disabled = False
dimming_started_at: Optional[float] = None
dimming_timer: Optional[threading.Timer] = None
dimming_cooldown_timer: Optional[threading.Timer] = None
DIMMING_MAX_DURATION_S = 5 * 60
DIMMING_COOLDOWN_S = 5 * 60
dimming_remaining: int = DIMMING_MAX_DURATION_S  # seconds left after Dim Down
dimming_lock = threading.Lock()
frame_count = 0

# Camera detection polling
_camera_detection_thread: Optional[threading.Thread] = None


# Camera settings
CAMERA_SETTINGS_FILE = "/home/Ento/LepmonOS/camera_web_settings.json"
DEFAULT_EXPOSURE = 140  # ms
DEFAULT_GAIN = 5
STREAM_DOWNSCALE = 8  # Downscale factor for streaming (reduces bandwidth)
STREAM_ZOOM = 1        # Center-crop zoom factor (1 = full frame, 2 = inner half, ...)

# Global camera settings (loaded from file)
camera_settings = {
    "exposure": DEFAULT_EXPOSURE,
    "gain": DEFAULT_GAIN,
    "stream_downscale": STREAM_DOWNSCALE,
    "stream_zoom": STREAM_ZOOM,
}


def sensor_defaults() -> dict:
    """Return a complete sensor payload for unavailable I2C readings."""
    return {
        "values": {
            "time_read": time.strftime("%Y-%m-%d %H:%M:%S"),
            "jetzt_local": "---",
            "LUX": "---",
            "Temp_in": "---",
            "bus_voltage": "---",
            "Temp_out": "---",
        },
        "status": {
            "rtc_status": 0,
            "Light_Sensor": 0,
            "Inner_Sensor": 0,
            "Power_Sensor": 0,
            "Environment_Sensor": 0,
        },
    }


def resolve_log_path() -> Optional[str]:
    """Resolve the path to the current LepmonOS log file.

    Resolution order:
      1. current_log from Lepmon_config.json (if file exists)
      2. Sample log in templates directory
    """
    from json_read_write import get_value_from_section
    log_file_path = "/home/Ento/LepmonOS/lepmonos.log"
    try:
        log_file_path = get_value_from_section(
            "/home/Ento/LepmonOS/Lepmon_config.json", "general", "current_log"
        )
        if not isinstance(log_file_path, str) or not log_file_path:
            log_file_path = "/home/Ento/LepmonOS/lepmonos.log"
    except Exception as e:
        logger.warning(f"Could not get log file path from config: {e}")

    if os.path.exists(log_file_path):
        return log_file_path

    sample_path = str(templates_dir / "Lepmon#SN000000_XX_YYY_Sample.log")
    if os.path.exists(sample_path):
        logger.info(f"Configured log path not found, using sample: {sample_path}")
        return sample_path

    return None


def resolve_csv_path() -> Optional[str]:
    """Resolve the path to the current LepmonOS CSV data file.

    Resolution order mirrors read_LepmonOS_csv():
      1. current_csv from Lepmon_config.json (if file exists)
      2. current_log from config with .log → .csv (if exists)
      3. Latest CSV inside a Lepmon#SN* directory on USB
      4. Sample CSV in templates directory
    """
    DEFAULT_CSV_PATH = str(templates_dir / "Lepmon#SN000000_XX_YYY_Sample.csv")
    from json_read_write import get_value_from_section

    # Step 1: explicit current_csv
    try:
        explicit_csv = get_value_from_section(
            "/home/Ento/LepmonOS/Lepmon_config.json", "general", "current_csv"
        )
        if isinstance(explicit_csv, str) and explicit_csv and os.path.exists(explicit_csv):
            return explicit_csv
    except Exception as e:
        logger.warning(f"Could not read current_csv from config: {e}")

    # Step 2: derive from current_log (.log → .csv)
    try:
        log_path = get_value_from_section(
            "/home/Ento/LepmonOS/Lepmon_config.json", "general", "current_log"
        )
        if isinstance(log_path, str) and log_path:
            derived = os.path.splitext(log_path)[0] + ".csv"
            if os.path.exists(derived):
                return derived
    except Exception as e:
        logger.warning(f"Could not derive CSV path from config: {e}")

    # Step 3: search USB stick
    usb_csv = _find_csv_on_usb()
    if usb_csv:
        return usb_csv

    # Step 4: sample CSV
    if os.path.exists(DEFAULT_CSV_PATH):
        return DEFAULT_CSV_PATH

    return None


def read_LepmonOS_log(log_mode: str = "web_stream") -> List[str]:
    """Read the configured LepmonOS log file and return its last 500 lines."""
    log_file_path = resolve_log_path()
    if log_file_path is None or not os.path.exists(log_file_path):
        return ["Log file not found."]

    try:
        with open(log_file_path, "r") as f:
            return f.readlines()[-500:]
    except Exception as e:
        logger.error(f"Could not read log file: {e}")
        return [f"Error reading log file: {e}"]

def read_LepmonOS_metadata(log_mode: str = "web_stream") -> dict:
    """Read the configured LepmonOS log file and return its metadata.

    Tries the path from Lepmon_config.json first.  If that file or key is
    missing, OR if the resolved path does not exist on disk, falls back to
    the default sample log so the web UI always has something to show.
    """
    DEFAULT_LOG_PATH = str(templates_dir / "Lepmon#SN000000_XX_YYY_Sample.log")
    log_file_path = "/home/Ento/LepmonOS/lepmonos.log"

    try:
        log_file_path = get_value_from_section(
            "/home/Ento/LepmonOS/Lepmon_config.json", "general", "current_log"
        )
    except Exception as e:
        logger.warning(f"Could not read log path from config: {e}")

    # Fall back when the resolved path does not exist on disk
    if not os.path.exists(log_file_path):
        logger.info(f"Configured log path does not exist: {log_file_path}")
        log_file_path = DEFAULT_LOG_PATH

    if not os.path.exists(log_file_path):
        return {"error": "Metadata file not found.", "log_file": log_file_path}

    try:
        with open(log_file_path, "r") as f:
            lines = f.readlines()
            if not lines:
                return {"error": "Metadata file is empty.", "log_file": log_file_path}
            header = "".join(lines[0:27]).strip()
            first_entries = "".join(lines[28:50]).strip()
            last_entries = "".join(lines[-15:]).strip()
            return {
                "log_file": log_file_path,
                "header": header,
                "first_entries": first_entries,
                "last_entries": last_entries,
                "total_lines": len(lines)
            }
    except Exception as e:
        logger.error(f"Could not read log file: {e}")
        return {"error": f"Error reading log file: {e}", "log_file": log_file_path}


def _find_csv_on_usb() -> Optional[str]:
    """Search the USB stick for the latest CSV inside a Lepmon#SN* directory.

    Used as a fallback when the config paths don't resolve (e.g. the
    config was written on a macOS machine with a different mount point).
    Returns the newest CSV path found, or None.
    """
    usb_path = _find_usb_mount_shared()
    if not usb_path:
        return None

    csv_files = []
    for root, dirs, files in os.walk(usb_path):
        # Only descend into Lepmon#SN* directories
        dirs[:] = [d for d in dirs if d.startswith("Lepmon#SN")]
        for f in files:
            if f.lower().endswith(".csv"):
                full = os.path.join(root, f)
                try:
                    csv_files.append((full, os.stat(full).st_mtime))
                except OSError:
                    pass

    if not csv_files:
        return None
    # Return the newest one
    csv_files.sort(key=lambda x: x[1], reverse=True)
    return csv_files[0][0]


def read_LepmonOS_csv() -> dict:
    """Read the CSV data file and return its metadata (header + first/last rows).

    Resolution order for the CSV path:
      1. current_csv from Lepmon_config.json (if file exists on disk)
      2. current_log from Lepmon_config.json with .log replaced by .csv (if exists)
      2.5 Latest CSV inside a Lepmon#SN* directory on the USB drive
      3. Sample CSV in the templates directory
    Both the sample CSV and real CSV share the same structure.
    """
    DEFAULT_CSV_PATH = str(templates_dir / "Lepmon#SN000000_XX_YYY_Sample.csv")
    csv_file_path = None

    # ── Step 1: Try explicit current_csv from config ──
    try:
        explicit_csv = get_value_from_section(
            "/home/Ento/LepmonOS/Lepmon_config.json", "general", "current_csv"
        )
        if isinstance(explicit_csv, str) and explicit_csv and os.path.exists(explicit_csv):
            csv_file_path = explicit_csv
            logger.info(f"Using CSV from config current_csv: {csv_file_path}")
    except Exception as e:
        logger.warning(f"Could not read current_csv from config: {e}")

    # ── Step 2: Fall back to deriving from current_log (.log → .csv) ──
    if csv_file_path is None:
        try:
            log_path = get_value_from_section(
                "/home/Ento/LepmonOS/Lepmon_config.json", "general", "current_log"
            )
            if isinstance(log_path, str) and log_path:
                derived = os.path.splitext(log_path)[0] + ".csv"
                if os.path.exists(derived):
                    csv_file_path = derived
                    logger.info(f"Using CSV derived from current_log: {csv_file_path}")
        except Exception as e:
            logger.warning(f"Could not derive CSV path from config: {e}")

    # ── Step 2.5: Search USB stick for CSV in Lepmon#SN* directories ──
    if csv_file_path is None:
        usb_csv = _find_csv_on_usb()
        if usb_csv:
            csv_file_path = usb_csv
            logger.info(f"Using CSV found on USB: {csv_file_path}")

    # ── Step 3: Fall back to sample CSV ──
    if csv_file_path is None:
        logger.info("No configured CSV found, falling back to sample CSV.")
        csv_file_path = DEFAULT_CSV_PATH

    if not os.path.exists(csv_file_path):
        return {"error": "CSV file not found.", "csv_file": csv_file_path}

    try:
        with open(csv_file_path, "r") as f:
            lines = f.readlines()
            if not lines:
                return {"error": "CSV file is empty.", "csv_file": csv_file_path}

            # CSV structure (shared between sample and real CSV):
            # Lines 1-23:   # comment metadata (software, machine, GPS, etc.)
            # Line 24:      ******************** separator
            # Line 25-26:   #Starting new Programme / #Local Time
            # Line 27:      column header row (tab-separated)
            # Lines 28+:    data rows (tab-separated)

            # Find the separator line (*********************) to split header/data
            separator_idx = None
            for i, line in enumerate(lines):
                if line.strip().startswith("*****"):
                    separator_idx = i
                    break

            if separator_idx is not None:
                # Header = metadata comments before separator
                header = "".join(lines[:separator_idx]).strip()
                # Data starts after "#Starting new Programme" and "#Local Time" lines
                # Find the column header row (first line that doesn't start with # or *)
                data_start = separator_idx + 1
                for i in range(separator_idx + 1, len(lines)):
                    stripped = lines[i].strip()
                    if stripped and not stripped.startswith("#") and not stripped.startswith("*"):
                        data_start = i
                        break

                first_rows = "".join(lines[data_start:data_start + 10]).strip()
                last_rows = "".join(lines[-10:]).strip()
            else:
                # No separator found – treat as plain CSV
                header = "".join(lines[:3]).strip()
                first_rows = "".join(lines[3:13]).strip()
                last_rows = "".join(lines[-10:]).strip()

            return {
                "csv_file": csv_file_path,
                "header": header,
                "first_entries": first_rows,
                "last_entries": last_rows,
                "total_lines": len(lines)
            }
    except Exception as e:
        logger.error(f"Could not read CSV file: {e}")
        return {"error": f"Error reading CSV file: {e}", "csv_file": csv_file_path}

def _stop_dimming(disable: bool = False) -> None:
    """Dim the light down. Preserve remaining time for resume via Dim Up."""
    global dimming_active, dimming_disabled, dimming_started_at, dimming_timer, dimming_remaining, dimming_cooldown_timer
    from Lights import dim_down

    dim_down()
    with dimming_lock:
        if dimming_started_at is not None:
            elapsed = time.time() - dimming_started_at
            dimming_remaining = max(0, int(DIMMING_MAX_DURATION_S - elapsed))
        dimming_active = False
        dimming_started_at = None
        dimming_timer = None
        if disable:
            # Timeout: enforce 5-minute cooldown before Dim Up is allowed again
            dimming_disabled = True
            dimming_remaining = 0
            if dimming_cooldown_timer is not None:
                dimming_cooldown_timer.cancel()
            dimming_cooldown_timer = threading.Timer(
                DIMMING_COOLDOWN_S, _enable_after_cooldown
            )
            dimming_cooldown_timer.daemon = True
            dimming_cooldown_timer.start()


def _enable_after_cooldown() -> None:
    """Re-enable Dim Up after the mandatory cooldown period."""
    global dimming_disabled, dimming_remaining, dimming_cooldown_timer
    with dimming_lock:
        dimming_disabled = False
        dimming_remaining = DIMMING_MAX_DURATION_S
        dimming_cooldown_timer = None


# ---------- Camera detection polling ----------

def _poll_camera_detection() -> None:
    """Background thread: poll camera presence every 2s and update config JSON.

    IMPORTANT: Do NOT use 'with VmbSystem.get_instance()' because the __exit__
    method can shut down the VmbSystem singleton, which would break the
    streaming thread that also relies on the same singleton.
    """
    from json_read_write import write_value_to_section
    CONFIG = "/home/Ento/LepmonOS/Lepmon_config.json"
    while True:
        detected = False
        try:
            from vmbpy import VmbSystem  # noqa: PLC0415
            vmb = VmbSystem.get_instance()
            try:
                cams = vmb.get_all_cameras()
                detected = bool(cams)
                logger.debug(f"Camera detection poll: found {len(cams) if cams else 0} camera(s)")
            except Exception as e:
                logger.debug(f"Camera detection get_all_cameras() failed: {e}")
        except ImportError:
            logger.debug("vmbpy not available for camera detection polling")
        except Exception as e:
            logger.debug(f"Camera detection poll failed: {e}")

        try:
            write_value_to_section(CONFIG, "Camera_state", "is_detected", detected)
        except Exception as e:
            logger.error(f"Failed to write camera detection to config: {e}")

        time.sleep(2)


def _start_camera_detection() -> None:
    """Launch the camera detection background thread."""
    global _camera_detection_thread
    if _camera_detection_thread is not None and _camera_detection_thread.is_alive():
        return
    _camera_detection_thread = threading.Thread(
        target=_poll_camera_detection, daemon=True
    )
    _camera_detection_thread.start()


def _stop_camera_detection() -> None:
    """Signal the detection thread to stop (handled by daemon flag on exit)."""
    global _camera_detection_thread
    _camera_detection_thread = None



def _start_dimming() -> bool:
    """Dim the light up. Resume from saved remaining time (no reset to 5 min)."""
    global dimming_active, dimming_disabled, dimming_started_at, dimming_timer, dimming_remaining
    from Lights import dim_up

    with dimming_lock:
        if dimming_disabled:
            return False
        if dimming_active:
            return True  # already active, nothing to do
        if dimming_remaining <= 0:
            return False  # no time left

    dim_up()

    with dimming_lock:
        dimming_active = True
        dimming_disabled = False
        dimming_started_at = time.time()

        # Cancel existing timer if any
        if dimming_timer is not None:
            dimming_timer.cancel()

        # Start timer with the *remaining* seconds (not always full 5 min)
        dimming_timer = threading.Timer(dimming_remaining, _stop_dimming, args=(True,))
        dimming_timer.daemon = True
        dimming_timer.start()

    return True


def _get_dimming_status() -> dict:
    """Return the current dimming state."""
    with dimming_lock:
        remaining = dimming_remaining
        if dimming_active and dimming_started_at is not None:
            elapsed = time.time() - dimming_started_at
            remaining = max(0, int(dimming_remaining - elapsed))
        return {
            "active": dimming_active,
            "disabled": dimming_disabled,
            "remaining": remaining,
        }



def load_camera_settings():
    """Load camera settings from JSON file."""
    global camera_settings
    try:
        if os.path.exists(CAMERA_SETTINGS_FILE):
            with open(CAMERA_SETTINGS_FILE, 'r') as f:
                loaded = json.load(f)
                camera_settings.update(loaded)
                logger.info(f"Loaded camera settings: {camera_settings}")
    except Exception as e:
        logger.warning(f"Could not load camera settings: {e}")

def save_camera_settings():
    """Save camera settings to JSON file."""
    try:
        with open(CAMERA_SETTINGS_FILE, 'w') as f:
            json.dump(camera_settings, f, indent=2)
        logger.info(f"Saved camera settings: {camera_settings}")
    except Exception as e:
        logger.error(f"Could not save camera settings: {e}")


def _dev_mode_frame() -> np.ndarray:
    note_mock("Allied Vision camera (vmbpy) for web streaming")
    return generate_mock_frame(640, 480, label="DEV MODE - stream")


def get_vimba_frame(exposure: int = DEFAULT_EXPOSURE, gain: float = DEFAULT_GAIN) -> Optional[np.ndarray]:
    """
    Capture a single frame from the Allied Vision camera using VmbPy SDK.
    Returns the frame as a numpy array, a DEV_MODE mock frame if no camera is
    found and DEV_MODE is on, or None if capture fails.
    """
    try:
        from vmbpy import VmbSystem, PixelFormat, PersistType

        with VmbSystem.get_instance() as vmb:
            cams = vmb.get_all_cameras()
            if not cams:
                logger.warning("No Allied Vision camera found")
                return _dev_mode_frame() if DEV_MODE else None

            with cams[0] as cam:
                # Don't force pixel format - use whatever camera supports
                # Most Allied Vision cameras default to Mono8 or BayerRG8

                # Load settings if available
                settings_file = '/home/Ento/LepmonOS/Kamera_Einstellungen_VimbaX.xml'
                if os.path.exists(settings_file):
                    try:
                        cam.load_settings(settings_file, PersistType.All)
                    except Exception as e:
                        logger.warning(f"Could not load camera settings: {e}")

                # Set exposure and gain
                try:
                    cam.ExposureTime.set(exposure * 1000)  # Convert to microseconds
                    cam.Gain.set(gain)
                except Exception as e:
                    logger.warning(f"Could not set exposure/gain: {e}")

                #check pixelformats:
                try:
                    logger.info(f"Current PixelFormat: {cam.get_pixel_format()}")
                except Exception as e:
                    logger.warning(f"Could not query pixel formats: {e}")

                # Capture frame
                frame = cam.get_frame(timeout_ms=5000).as_opencv_image()
                return frame

    except ImportError:
        logger.error("VmbPy SDK not available - using test pattern")
        return _dev_mode_frame() if DEV_MODE else None
    except Exception as e:
        logger.error(f"Error capturing frame: {e}")
        return _dev_mode_frame() if DEV_MODE else None


def generate_test_pattern() -> np.ndarray:
    """Generate a test pattern for development/testing when camera is not available."""
    height, width = 480, 640
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    
    # Create gradient pattern
    for i in range(height):
        frame[i, :, 0] = int(255 * i / height)  # Blue gradient
        frame[i, :, 2] = int(255 * (height - i) / height)  # Red gradient
    
    # Add timestamp
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    cv2.putText(frame, f"Test Pattern - {timestamp}", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    cv2.putText(frame, "Camera not available", (10, 60),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
    
    return frame


def apply_min_max_stretch(frame: np.ndarray) -> np.ndarray:
    """
    Apply min/max contrast stretch to enhance image visibility.
    This normalizes the image histogram to use the full dynamic range.
    Handles both grayscale and color images.
    """
    if frame is None:
        return None
    
    # Handle grayscale images - convert to BGR first
    if len(frame.shape) == 2 or (len(frame.shape) == 3 and frame.shape[2] == 1):
        frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
    
    # Convert to float for processing
    frame_float = frame.astype(np.float32)
    
    # Apply min/max stretch per channel
    for i in range(3):
        channel = frame_float[:, :, i]
        min_val = np.percentile(channel, 1)  # Use 1st percentile to avoid outliers
        max_val = np.percentile(channel, 99)  # Use 99th percentile to avoid outliers
        
        if max_val > min_val:
            channel = (channel - min_val) / (max_val - min_val) * 255
            channel = np.clip(channel, 0, 255)
            frame_float[:, :, i] = channel
    
    return frame_float.astype(np.uint8)


def calculate_focus_score(frame: np.ndarray) -> float:
    """
    Calculate the focus score using Variance of Laplacian method.
    Higher values indicate sharper images.
    """
    if frame is None:
        return 0.0
    
    # Convert to grayscale if needed
    if len(frame.shape) == 3 and frame.shape[2] == 3:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    elif len(frame.shape) == 3 and frame.shape[2] == 1:
        gray = frame[:, :, 0]  # Extract single channel
    else:
        gray = frame  # Already grayscale
    
    laplacian = cv2.Laplacian(gray, cv2.CV_64F)
    variance = laplacian.var()
    return float(variance)


def calculate_brightness(frame: np.ndarray) -> float:
    """Calculate average brightness of the frame."""
    if frame is None:
        return 0.0
    
    # Convert to grayscale if needed
    if len(frame.shape) == 3 and frame.shape[2] == 3:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    elif len(frame.shape) == 3 and frame.shape[2] == 1:
        gray = frame[:, :, 0]  # Extract single channel
    else:
        gray = frame  # Already grayscale
    
    return float(gray.mean())


def frame_generator() -> Generator[bytes, None, None]:
    """
    Generator function for MJPEG streaming.
    Captures frames from camera, applies min/max stretch, and yields JPEG data.

    The camera is only touched while a web focus session is active
    (set by the OLED "Web Focus" menu entry) AND no timelapse is running.
    Otherwise the stream closes so the browser can show its placeholder.
    """
    global current_frame, streaming_active, stream_consumers

    with stream_consumers_lock:
        stream_consumers += 1
        streaming_active = True

    logger.info(f"Stream consumer connected. Total consumers: {stream_consumers}")

    # Persistent camera handle for the lifetime of this streaming session —
    # re-opening VmbSystem/the camera on every single frame (as get_vimba_frame
    # does for snapshots) is far too slow for smooth MJPEG playback.
    vmb = None
    cam_cm = None
    cam = None

    def _close_camera():
        nonlocal vmb, cam_cm, cam
        if cam_cm is not None:
            try:
                cam_cm.__exit__(None, None, None)
            except Exception as e:
                logger.warning(f"Error closing camera: {e}")
            cam_cm = None
            cam = None
        if vmb is not None:
            try:
                vmb.__exit__(None, None, None)
            except Exception as e:
                logger.warning(f"Error closing VmbSystem: {e}")
            vmb = None

    def _open_camera(exposure, gain):
        nonlocal vmb, cam_cm, cam
        from vmbpy import VmbSystem, PersistType

        vmb = VmbSystem.get_instance()
        vmb.__enter__()
        cams = vmb.get_all_cameras()
        if not cams:
            vmb.__exit__(None, None, None)
            vmb = None
            return None

        cam_cm = cams[0]
        cam = cam_cm.__enter__()

        settings_file = '/home/Ento/LepmonOS/Kamera_Einstellungen_VimbaX.xml'
        if os.path.exists(settings_file):
            try:
                cam.load_settings(settings_file, PersistType.All)
            except Exception as e:
                logger.warning(f"Could not load camera settings: {e}")
        try:
            cam.ExposureTime.set(exposure * 1000)
            cam.Gain.set(gain)
        except Exception as e:
            logger.warning(f"Could not set exposure/gain: {e}")

        return cam

    try:
        # Use global camera settings
        exposure = camera_settings["exposure"]
        gain = camera_settings["gain"]
        downscale = camera_settings.get("stream_downscale", STREAM_DOWNSCALE)
        zoom = camera_settings.get("stream_zoom", STREAM_ZOOM)

        while True:
            '''
            state = get_capturing_state()

            # Timelapse wins — never compete with it.
            if state.is_capturing:
                _close_camera()
                logger.info("Stream unavailable: capture is in progress")
                return
            '''
            # Derive all camera state from Lepmon_config.json via get_value_from_section
            is_capturing = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "Camera_state", "is_capturing")
            has_power = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "Camera_state", "has_power")
            free_for_web = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "Camera_state", "free_for_web")

            if is_capturing:
                _close_camera()
                logger.info("Stream unavailable: camera is capturing an image")
                frame_count = 0
                return
            
            if not free_for_web:
                _close_camera()
                logger.info("Stream unavailable: camera is not free for web streaming")
                frame_count = 0
                return

            # Capture frame from the persistent camera handle (opened once).
            frame = None
            try:
                with camera_lock:
                    if cam is None:
                        _open_camera(exposure, gain)
                    if cam is not None:
                        frame = cam.get_frame(timeout_ms=5000).as_opencv_image()
            except Exception as e:
                logger.error(f"Error capturing stream frame: {e}")
                print("Error capturing stream frame:", e)
                _close_camera()
                frame = _dev_mode_frame() if DEV_MODE else None

            if frame is not None:
                # 1) Center-crop zoom first (before downscale, for accuracy)
                if zoom > 1:
                    h, w = frame.shape[:2]
                    crop_h = max(1, h // zoom)
                    crop_w = max(1, w // zoom)
                    y_start = (h - crop_h) // 2
                    x_start = (w - crop_w) // 2
                    frame = frame[y_start:y_start + crop_h, x_start:x_start + crop_w]

                # 2) Downscale to reduce processing time
                h, w = frame.shape[:2]
                if downscale > 1:
                    new_w = w // downscale
                    new_h = h // downscale
                    frame = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)
                
                # Apply min/max stretch for better visibility
                stretched = apply_min_max_stretch(frame)
                
                # Calculate and overlay focus score (use original scale for accuracy)
                focus_score = calculate_focus_score(frame)
                brightness = calculate_brightness(frame)
                
                # Resize for streaming if still too large (> 1280px wide)
                h, w = stretched.shape[:2]
                if w > 1280:
                    scale = 1280 / w
                    stretched = cv2.resize(stretched, (int(w * scale), int(h * scale)))
                
                # Add overlay information
                cv2.putText(stretched, f"Focus: {focus_score:.1f}", (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                cv2.putText(stretched, f"Brightness: {brightness:.1f}", (10, 60),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                cv2.putText(stretched, f"frame: {frame_count}", (10, 90),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                cv2.putText(stretched, f"zoom: {zoom}, downscale: {downscale}", (10, 90),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                
                
                current_frame = stretched
                
                # Encode to JPEG
                _, jpeg = cv2.imencode('.jpg', stretched, [cv2.IMWRITE_JPEG_QUALITY, 80])
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')
            else:
                logger.error("Stream unavailable: camera returned no frame")
                return
            
            # Frame rate control (~5 FPS for preview)
            time.sleep(0.2)
            
    except GeneratorExit:
        logger.info("Stream consumer disconnected")
    finally:
        _close_camera()
        with stream_consumers_lock:
            stream_consumers -= 1
            if stream_consumers <= 0:
                streaming_active = False
                stream_consumers = 0
        logger.info(f"Stream consumer disconnected. Remaining consumers: {stream_consumers}")


def create_status_frame(message: str) -> np.ndarray:
    """Create a status frame with a message."""
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    frame[:, :] = (40, 40, 40)  # Dark gray background
    
    # Add Lepmon branding
    cv2.putText(frame, "LEPMON", (220, 200),
                cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 255, 0), 3)
    cv2.putText(frame, message, (50, 280),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
    cv2.putText(frame, time.strftime("%Y-%m-%d %H:%M:%S"), (200, 320),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (128, 128, 128), 1)
    
    return frame


# FastAPI Application
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("Lepmon Web Service starting...")
    load_camera_settings()
    yield
    logger.info("Lepmon Web Service shutting down...")


app = FastAPI(
    title="Lepmon Web Service",
    description="Camera streaming and monitoring service for Lepmon insect monitoring system",
    version="1.0.0",
    lifespan=lifespan,
    # We serve Swagger UI from a vendored bundle below so the device
    # works without internet access.
    docs_url=None,
    redoc_url=None,
)

# Setup templates
templates_dir = Path(__file__).parent / "templates"
templates_dir.mkdir(exist_ok=True)
templates = Jinja2Templates(directory=str(templates_dir))

# Vendored frontend assets (Swagger UI bundle, etc.). The install script
# downloads these into static/ during SD card build; if missing, the
# /docs route still responds with a friendly hint instead of 500-ing.
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


def _swagger_assets_present() -> bool:
    return (static_dir / "swagger-ui-bundle.js").is_file() and \
           (static_dir / "swagger-ui.css").is_file()


@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui():
    """Serve the Swagger UI from local assets — no CDN required."""
    if not _swagger_assets_present():
        return HTMLResponse(
            "<h1>Swagger UI assets not installed</h1>"
            "<p>Run install_lepmon.sh or place "
            "<code>swagger-ui-bundle.js</code> and <code>swagger-ui.css</code> "
            "into the <code>static/</code> directory next to "
            "<code>lepmon_web_service.py</code>.</p>",
            status_code=503,
        )
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} – API",
        swagger_js_url="/static/swagger-ui-bundle.js",
        swagger_css_url="/static/swagger-ui.css",
        swagger_favicon_url="/static/favicon.ico",
    )


@app.get("/redoc", include_in_schema=False)
async def custom_redoc():
    """ReDoc served from the local bundle if available."""
    if not (static_dir / "redoc.standalone.js").is_file():
        return HTMLResponse(
            "<h1>ReDoc not installed</h1>"
            "<p>Place <code>redoc.standalone.js</code> in <code>static/</code>.</p>",
            status_code=503,
        )
    return get_redoc_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} – ReDoc",
        redoc_js_url="/static/redoc.standalone.js",
        redoc_favicon_url="/static/favicon.ico",
    )


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Serve the main web interface."""
    return templates.TemplateResponse(request, "index.html", {
        "title": "Lepmon Camera Monitor"
    })


@app.get("/LEPMON_Logo_Circle.png")
async def logo():
    """Serve the camera-stream placeholder image."""
    return FileResponse(templates_dir / "LEPMON_Logo_Circle.png")


@app.get("/Capture_Image.png")
async def capture_image_placeholder():
    """Serve the capture placeholder image."""
    return FileResponse(templates_dir / "Capture_Image.png")


@app.get("/stream")
async def video_stream():
    """MJPEG video stream endpoint. Only served when focus session allows it."""
    try:
        free_for_web = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "Camera_state", "free_for_web")
        web_requested = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "Camera_state", "web_requested")
        is_capturing = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "Camera_state", "is_capturing")
    except Exception:
        free_for_web = False
        web_requested = False
        is_capturing = False

    if not (free_for_web and web_requested):
        logger.info("Stream blocked: camera not free or not requested for web")
        placeholder = "/Capture_Image.png" if is_capturing else "/LEPMON_Logo_Circle.png"
        return RedirectResponse(url=placeholder)

    return StreamingResponse(
        frame_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )

LEPMON_CONFIG_PATH = "/home/Ento/LepmonOS/Lepmon_config.json"


@app.get("/api/camera/power")
async def get_camera_power():
    """Return Camera_state.has_power from Lepmon_config.json."""
    try:
        has_power = get_value_from_section(LEPMON_CONFIG_PATH, "Camera_state", "has_power")
    except Exception:
        has_power = False
    return {"has_power": bool(has_power)}


@app.get("/api/camera/state")
async def get_camera_state():
    """Return all Camera_state control parameters from Lepmon_config.json."""
    try:
        return {
            "has_power": bool(get_value_from_section(LEPMON_CONFIG_PATH, "Camera_state", "has_power")),
            "is_detected": bool(get_value_from_section(LEPMON_CONFIG_PATH, "Camera_state", "is_detected")),
            "is_capturing": bool(get_value_from_section(LEPMON_CONFIG_PATH, "Camera_state", "is_capturing")),
            "free_for_web": bool(get_value_from_section(LEPMON_CONFIG_PATH, "Camera_state", "free_for_web")),
            "web_requested": bool(get_value_from_section(LEPMON_CONFIG_PATH, "Camera_state", "web_requested")),
        }
    except Exception:
        return {
            "has_power": False,
            "is_detected": False,
            "is_capturing": False,
            "free_for_web": False,
            "web_requested": False,
        }




@app.post("/api/dimming/up")
async def api_dim_up():
    """Turn the visible LED on (dim up) and start the 5-minute safety timer."""
    try:
        success = _start_dimming()
        if not success:
            return JSONResponse(
                {"error": "Dimming is disabled (max duration reached). Press Dim Down to reset."},
                status_code=409
            )
        status = _get_dimming_status()
        return {"success": True, "active": True, "remaining": status["remaining"]}
    except Exception as e:
        logger.error(f"Dim up failed: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/dimming/down")
async def api_dim_down():
    """Turn the visible LED off (dim down) and reset the timer."""
    try:
        _stop_dimming(disable=False)
        return {"success": True, "active": False}
    except Exception as e:
        logger.error(f"Dim down failed: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/dimming/status")
async def api_dimming_status():
    """Get the current dimming state (active, disabled, remaining seconds)."""
    return _get_dimming_status()


@app.get("/snapshot")
async def snapshot():
    """Capture and return a single JPEG snapshot."""
    state = get_capturing_state()
    if state.is_capturing:
        return JSONResponse(
            {"error": "Cannot capture snapshot while capturing is active"},
            status_code=503
        )
    
    with camera_lock:
        frame = get_vimba_frame()
    
    if frame is None:
        return JSONResponse({"error": "Failed to capture frame"}, status_code=500)
    
    # Apply min/max stretch
    stretched = apply_min_max_stretch(frame)
    
    # Encode to JPEG
    _, jpeg = cv2.imencode('.jpg', stretched, [cv2.IMWRITE_JPEG_QUALITY, 95])
    
    return Response(
        content=jpeg.tobytes(),
        media_type="image/jpeg",
        headers={"Content-Disposition": "inline; filename=lepmon_snapshot.jpg"}
    )


@app.get("/api/status")
async def get_status():
    """Get current system status."""
    state = get_capturing_state()

    # Camera state from config — single source of truth for all Camera_state fields
    try:
        camera_has_power = get_value_from_section(LEPMON_CONFIG_PATH, "Camera_state", "has_power")
        camera_is_detected = get_value_from_section(LEPMON_CONFIG_PATH, "Camera_state", "is_detected")
        camera_is_capturing = get_value_from_section(LEPMON_CONFIG_PATH, "Camera_state", "is_capturing")
        camera_free_for_web = get_value_from_section(LEPMON_CONFIG_PATH, "Camera_state", "free_for_web")
        camera_web_requested = get_value_from_section(LEPMON_CONFIG_PATH, "Camera_state", "web_requested")
    except Exception:
        camera_has_power = False
        camera_is_detected = False
        camera_is_capturing = False
        camera_free_for_web = False
        camera_web_requested = False

    return {
        "is_capturing": bool(camera_is_capturing),
        "capture_start_time": state.start_time.isoformat() if state.start_time else None,
        "images_captured": state.images_captured,
        "stream_active": streaming_active,
        "stream_consumers": stream_consumers,
        "stop_focus_requested": state.stop_focus_requested,
        "camera_has_power": bool(camera_has_power),
        "is_detected": bool(camera_is_detected),
        "free_for_web": bool(camera_free_for_web),
        "web_requested": bool(camera_web_requested),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }


@app.get("/api/sensors")
async def get_sensors():
    """Read and return the current I2C sensor values for the web monitor."""
    try:
        from sensor_data import read_sensor_data
        from times import Zeit_aktualisieren

        jetzt_local, _, rtc_status = Zeit_aktualisieren(log_mode="web_stream")

        sensor_values, sensor_status = read_sensor_data(
            "web_monitor", time.strftime("%Y-%m-%d %H:%M:%S"), "web_stream"
        )
        sensor_values["jetzt_local"] = jetzt_local
        sensor_status["rtc_status"] = rtc_status
        return {"values": sensor_values, "status": sensor_status}
    except Exception as e:
        logger.error(f"Could not read sensor data: {e}")
        return sensor_defaults()




@app.post("/api/focus/stop")
async def request_focus_stop():
    """
    Ask the OLED loop to end the active web focus session.

    The OLED polling loop sees the flag and returns to the main menu.
    Safe to call repeatedly or when no session is active.
    """
    request_stop_focus()
    return {"message": "Stop request sent"}


@app.get("/api/camera/info")
async def camera_info():
    """Get camera information."""
    try:
        from vmbpy import VmbSystem
        
        with VmbSystem.get_instance() as vmb:
            cams = vmb.get_all_cameras()
            if cams:
                with cams[0] as cam:
                    return {
                        "available": True,
                        "model": cam.get_model(),
                        "serial": cam.get_serial(),
                        "interface_id": cam.get_interface_id(),
                        "is_detected": True
                    }
            else:
                return {"available": False, "error": "No camera found", "is_detected": False}
    except ImportError:
        return {"available": False, "error": "VmbPy SDK not installed", "is_detected": False}
    except Exception as e:
        return {"available": False, "error": str(e), "is_detected": False}


@app.get("/api/focus")
async def get_focus_score():
    """Get current focus score without capturing a new frame."""
    global current_frame
    
    if current_frame is not None:
        score = calculate_focus_score(current_frame)
        return {"focus_score": score, "is_sharp": score >= 225.0}
    else:
        return {"focus_score": 0.0, "is_sharp": False, "error": "No frame available"}


@app.get("/api/camera/settings")
async def get_camera_settings():
    """Get current camera settings."""
    return camera_settings


@app.post("/api/camera/settings")
async def update_camera_settings(settings: dict):
    """Update camera settings and save to file.

    Supported keys:
      - exposure    (float, 1-10000 ms)
      - gain        (float, 0-48 dB)
      - stream_downscale  (int, 1-20)
      - stream_zoom       (int, 1-5)
    """
    global camera_settings

    try:
        # Validate and update settings
        if "exposure" in settings:
            exposure = float(settings["exposure"])
            if 1 <= exposure <= 10000:
                camera_settings["exposure"] = exposure
            else:
                return JSONResponse(
                    {"error": "Exposure must be between 1 and 10000 ms"},
                    status_code=400
                )

        if "gain" in settings:
            gain = float(settings["gain"])
            if 0 <= gain <= 48:
                camera_settings["gain"] = gain
            else:
                return JSONResponse(
                    {"error": "Gain must be between 0 and 48"},
                    status_code=400
                )

        # Stream downscale factor (1 = no downscale, up to 20)
        if "stream_downscale" in settings:
            ds = int(settings["stream_downscale"])
            if 1 <= ds <= 20:
                camera_settings["stream_downscale"] = ds
            else:
                return JSONResponse(
                    {"error": "stream_downscale must be between 1 and 20"},
                    status_code=400
                )

        # Center-crop zoom factor (1 = full frame, up to 5)
        if "stream_zoom" in settings:
            z = int(settings["stream_zoom"])
            if 1 <= z <= 5:
                camera_settings["stream_zoom"] = z
            else:
                return JSONResponse(
                    {"error": "stream_zoom must be between 1 and 5"},
                    status_code=400
                )

        # Save to file
        save_camera_settings()

        return {
            "success": True,
            "settings": camera_settings
        }
    except ValueError as e:
        return JSONResponse(
            {"error": f"Invalid value: {str(e)}"},
            status_code=400
        )


@app.post("/api/capture/stop")
async def request_capture_stop():
    """Request the capturing loop to stop (for emergency/debugging)."""
    # This is a soft request - the main loop checks this flag
    from capturing_state import request_stop_capture
    request_stop_capture()
    return {"message": "Stop request sent"}


# ---------------------------------------------------------------------------
# Captured Images Gallery - serve latest images from USB drive
# ---------------------------------------------------------------------------

# find_usb_mount + _thumb_path_for live in thumbnail_utils so the capture
# loop can use them without importing FastAPI.
find_usb_mount = _find_usb_mount_shared


def find_latest_images(count: int = 10) -> List[dict]:
    """
    Recursively find the latest `count` image files on the USB drive.
    Only descends into directories whose name starts with "Lepmon#SN"
    so that test images, trash contents, and other non-capture files
    are excluded from the gallery.
    The .thumbs/ shadow tree is skipped so precomputed previews don't
    show up in the gallery as their own entries.
    """
    usb_path = find_usb_mount()
    if not usb_path:
        return []

    image_extensions = ('.jpg', '.jpeg', '.png', '.tif', '.tiff', '.bmp')
    images = []

    for root, dirs, files in os.walk(usb_path):
        # Only descend into Lepmon#SN* directories (and the top-level USB root)
        dirs[:] = [
            d for d in dirs
            if d != THUMBS_DIR_NAME
            and not d.lower().startswith("._")
            and (root == usb_path or d.startswith("Lepmon#SN"))
        ]
        for f in files:
            if f.lower().startswith("._"):  # Skip macOS resource forks
                continue
            if f.lower().endswith(image_extensions):
                full_path = os.path.join(root, f)
                try:
                    stat = os.stat(full_path)
                    images.append({
                        "path": full_path,
                        "filename": f,
                        "modified": stat.st_mtime,
                        "size": stat.st_size
                    })
                except OSError:
                    continue

    # Sort by modification time, newest first
    images.sort(key=lambda x: x["modified"], reverse=True)
    return images[:count]


@app.get("/api/images/latest")
async def get_latest_images(count: int = 10):
    """
    Return metadata for the latest captured images on the USB drive.
    Query param: count (default 10, max 50)
    """
    count = min(max(1, count), 50)
    images = find_latest_images(count)

    result = []
    for img in images:
        # URL-encode the path so special chars like '#' don't break query params
        safe_path = urlquote(img["path"], safe="")
        from datetime import datetime
        mod_time = datetime.fromtimestamp(img["modified"])
        result.append({
            "filename": img["filename"],
            "url": f"/api/images/file?path={safe_path}",
            "thumbnail_url": f"/api/images/thumbnail?path={safe_path}",
            "modified": mod_time.isoformat(),
            "size_kb": round(img["size"] / 1024, 1)
        })

    usb_path = find_usb_mount()
    return {
        "images": result,
        "usb_mounted": usb_path is not None,
        "usb_path": usb_path,
        "total_found": len(result)
    }


@app.get("/api/log")
async def get_log():
    """Return the latest lines from the configured LepmonOS log."""
    return {"lines": read_LepmonOS_log()}


@app.get("/api/download/log")
async def download_log():
    """Download the raw LepmonOS log file."""
    log_file_path = resolve_log_path()
    if log_file_path is None or not os.path.isfile(log_file_path):
        return JSONResponse({"error": "No log file found."}, status_code=404)

    filename = os.path.basename(log_file_path)
    try:
        with open(log_file_path, "rb") as f:
            content = f.read()
    except OSError as e:
        logger.warning(f"Failed to read log file {log_file_path} (USB hot-unplug?): {e}")
        return JSONResponse({"error": "Log file disappeared (USB disconnected?)."}, status_code=503)
    return Response(
        content=content,
        media_type="text/plain",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.get("/api/csv")
async def read_csv_file():
    """Return structured metadata (header + first/last entries) from the CSV data file.

    Reads the actual CSV file and returns a JSON object with:
      - csv_file: path to the CSV file being displayed
      - header: metadata comment block (lines 1–N before separator)
      - first_entries: column header + first 10 data rows
      - last_entries: last 10 data rows
      - total_lines: total line count of the file

    Falls back to the sample CSV when no real data file exists.
    On failure, returns { error: "...", csv_file: "..." }.
    """
    meta = read_LepmonOS_csv()
    if meta.get("error"):
        # Return the error directly so the frontend can detect data.error.
        return {
            "error": meta["error"],
            "csv_file": meta.get("csv_file", "unknown"),
        }
    # Pass through the structured response unchanged.
    return meta


@app.get("/api/download/csv")
async def download_csv():
    """Download the raw CSV data file."""
    csv_file_path = resolve_csv_path()
    if not csv_file_path or not os.path.isfile(csv_file_path):
        return JSONResponse({"error": "CSV file not found."}, status_code=404)

    filename = os.path.basename(csv_file_path)
    try:
        with open(csv_file_path, "rb") as f:
            content = f.read()
    except OSError as e:
        logger.warning(f"Failed to read CSV file {csv_file_path} (USB hot-unplug?): {e}")
        return JSONResponse({"error": "CSV file disappeared (USB disconnected?)."}, status_code=503)
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )

@app.get("/api/images/file")
async def serve_image(path: str):
    """Serve an image file from the USB drive."""
    # Security: only serve files under a mounted USB drive.
    if not is_usb_path(path):
        return JSONResponse({"error": "Access denied"}, status_code=403)
    if not os.path.isfile(path):
        return JSONResponse({"error": "File not found"}, status_code=404)

    ext = os.path.splitext(path)[1].lower()
    mime_map = {
        '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
        '.png': 'image/png', '.tif': 'image/tiff',
        '.tiff': 'image/tiff', '.bmp': 'image/bmp'
    }
    mime = mime_map.get(ext, 'application/octet-stream')

    try:
        with open(path, 'rb') as f:
            data = f.read()
    except OSError as e:
        logger.warning(f"Failed to serve image {path} (USB hot-unplug?): {e}")
        return JSONResponse({"error": "Image disappeared (USB disconnected?)."}, status_code=503)

    return Response(content=data, media_type=mime)


@app.get("/api/images/thumbnail")
async def serve_thumbnail(path: str, max_size: int = THUMB_MAX_PX):
    """
    Serve a downscaled thumbnail of an image from the USB drive.

    Prefers a precomputed JPEG from the .thumbs/ shadow tree (written
    by the capture loop). Falls back to a lazy 16-bit-aware decode,
    caching the result for next time.
    """
    if not is_usb_path(path):
        return JSONResponse({"error": "Access denied"}, status_code=403)

    try:
        if not os.path.isfile(path):
            return JSONResponse({"error": "File not found"}, status_code=404)
    except OSError as e:
        logger.warning(f"Thumbnail path check failed {path} (USB hot-unplug?): {e}")
        return JSONResponse({"error": "USB disconnected during request."}, status_code=503)

    thumb_path = _thumb_path_for(path)

    if thumb_path and os.path.isfile(thumb_path):
        try:
            with open(thumb_path, 'rb') as f:
                return Response(content=f.read(), media_type="image/jpeg")
        except OSError as e:
            logger.warning(f"Failed to serve cached thumbnail {thumb_path}: {e}")

    try:
        data = _make_thumbnail(path, max_size)
        if data is None:
            return JSONResponse({"error": "Cannot read image"}, status_code=500)

        # Best-effort cache write so subsequent requests are cheap.
        if thumb_path:
            try:
                os.makedirs(os.path.dirname(thumb_path), exist_ok=True)
                with open(thumb_path, 'wb') as f:
                    f.write(data)
            except OSError as e:
                logger.warning(f"Could not cache thumbnail {thumb_path}: {e}")

        return Response(content=data, media_type="image/jpeg")
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/storage")
async def get_storage_info():
    """Return USB disk usage information."""
    usb_path = find_usb_mount()
    if not usb_path:
        return {"mounted": False}
    try:
        st = os.statvfs(usb_path)
        total = st.f_frsize * st.f_blocks
        free = st.f_frsize * st.f_bfree
        available = st.f_frsize * st.f_bavail
        used = total - free
        gb = 1024 ** 3
        return {
            "mounted": True,
            "path": usb_path,
            "total_gb": round(total / gb, 2),
            "used_gb": round(used / gb, 2),
            "available_gb": round(available / gb, 2),
            "used_percent": round(used / total * 100, 1) if total else 0,
            "available_percent": round(available / total * 100, 1) if total else 0,
        }
    except Exception as e:
        logger.error(f"Storage info error: {e}")
        return {"mounted": True, "error": str(e)}


@app.get("/api/timing")
async def get_timing_info():
    """Return full experiment timing + location + USB data object.

    Delegates to lepmon_web_tables.get_web_table_object() which collects:
    - Sun times (sunset, sunrise)
    - Experiment times (start/end capture)
    - Power times (attiny ON/OFF)
    - Config offsets
    - GPS coordinates, locality (province/city)
    - USB stick storage info
    - Current pipeline step (start_up / capturing / wait / end / local_menu)
    """
    try:
        from lepmon_web_tables import get_web_table_object
        return get_web_table_object(log_mode="web_stream")
    except Exception as e:
        logger.error(f"Timing info error: {e}")
        return {"error": str(e)}


@app.get("/api/location")
async def get_location_info():
    """Return GPS coordinates and locality data (province/city).

    Uses the shared web_table_object but returns only location fields.
    """
    try:
        from lepmon_web_tables import get_web_table_object
        data = get_web_table_object(log_mode="web_stream")
        return {
            "latitude": data.get("latitude"),
            "longitude": data.get("longitude"),
            "pol": data.get("pol", ""),
            "block": data.get("block", ""),
            "province": data.get("province", "---"),
            "city": data.get("city", "---"),
            "country": data.get("country", "---"),
        }
    except Exception as e:
        logger.error(f"Location info error: {e}")
        return {"error": str(e)}


def run_server(host: str = "0.0.0.0", port: int = 8080):
    """Run the FastAPI server."""
    uvicorn.run(app, host=host, port=port, log_level="info")


def start_background_server(host: str = "0.0.0.0", port: int = 8080):
    """Start the server in a background thread."""
    server_thread = threading.Thread(
        target=run_server,
        args=(host, port),
        daemon=True,
        name="LepmonWebService"
    )
    server_thread.start()
    logger.info(f"Lepmon Web Service started on http://{host}:{port}")
    return server_thread


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Lepmon Web Service")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8080, help="Port to bind to")
    args = parser.parse_args()
    # Start camera detection polling (2s interval)
    _start_camera_detection()

    
    run_server(args.host, args.port)