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
import ssl
import subprocess
import threading
import time
import uuid
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
from hardware import get_hardware_version
from picamera2 import Picamera2, Preview
from libcamera import controls
from json_read_write import get_value_from_section, write_value_to_section, get_camera_state, set_camera_state, set_stream_viewers
from viewer_state import set_viewer_count, get_viewer_count
# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
HARDWARE_VERSION = get_hardware_version()

if HARDWARE_VERSION in ["Pro_Gen_1", "Pro_Gen_2", "Pro_Gen_3", "Pro_Gen_4"]:
    EXPECTED_CAMERA_TYPE = "AV"
elif HARDWARE_VERSION in ["CSS_Gen_1"]:
    EXPECTED_CAMERA_TYPE = "RPI"

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


# ─── Stream Viewer / Client Registry ──────────────────────────────────────────
# Tracks all active web clients (browser tabs) regardless of stream state.
# Each client registers on page load and sends periodic heartbeats (every 5s).
# Clients that don't send a heartbeat within HEARTBEAT_TIMEOUT are auto-removed
# by a background cleanup thread (handles abrupt disconnect / Wi-Fi loss).
_CLIENT_REGISTRY: dict = {}  # token (str) → last_seen (float)
_CLIENT_REGISTRY_LOCK = threading.Lock()
HEARTBEAT_TIMEOUT = 30  # seconds without heartbeat → client considered gone
_CLEANUP_INTERVAL = 10  # cleanup thread runs every 10 seconds
_cleanup_running = False


def _viewer_cleanup_loop():
    """Background thread: removes stale clients that lost connectivity."""
    global _cleanup_running
    while _cleanup_running:
        time.sleep(_CLEANUP_INTERVAL)
        now = time.time()
        with _CLIENT_REGISTRY_LOCK:
            stale_tokens = [t for t, ts in _CLIENT_REGISTRY.items() if (now - ts) > HEARTBEAT_TIMEOUT]
            if stale_tokens:
                for t in stale_tokens:
                    del _CLIENT_REGISTRY[t]
                new_count = len(_CLIENT_REGISTRY)
                logger.info(f"Viewer cleanup: removed {len(stale_tokens)} stale viewer(s). Remaining: {new_count}")
                set_stream_viewers(new_count)
                set_viewer_count(new_count)


def _start_viewer_cleanup():
    """Start the viewer cleanup background thread."""
    global _cleanup_running
    _cleanup_running = True
    t = threading.Thread(target=_viewer_cleanup_loop, daemon=True, name="viewer-cleanup")
    t.start()
    logger.info("Viewer heartbeat cleanup thread started")


def _stop_viewer_cleanup():
    global _cleanup_running
    _cleanup_running = False


# Camera detection polling
_camera_detection_thread: Optional[threading.Thread] = None

# Cached camera info (populated when streaming opens the camera)
_last_camera_model: Optional[str] = None
_last_camera_serial: Optional[str] = None
_last_camera_detected: bool = False
stream_frame_count: int = 0


# ─── Shared Camera Handler + Background Grabbing Thread ─────────────────────
# vmbpy enforces that get_frame() must be called within the SAME stack frame
# as the 'with cams[0] as cam:' block. Calling grab_frame() from another
# thread/generator FAILS with "outside of 'with' context".
#
# Solution: A dedicated background thread holds the 'with cams[0] as cam:'
# block for the entire streaming session. It grabs raw frames and stores them
# in _latest_frame (protected by _frame_lock). All MJPEG generators read this
# shared frame via .copy(), so no queue contention occurs.
#
# This eliminates ALL three error types:
#   - "Camera already in use" (AccessMode.Full conflict)
#   - BadHandle / BadParameter (SDK state corruption)
#   - "get_frame() outside of 'with' context"
#
# Shared latest-frame pattern: background thread writes, all generators read
# (via copy). Every consumer sees the same latest frame instead of fighting
# over a single queue item — no starvation, no "Waiting for camera" timeouts.
_latest_frame: Optional[np.ndarray] = None
_frame_lock = threading.Lock()

# Background grabbing thread state
_grab_thread: Optional[threading.Thread] = None
_grab_running = False

# Lock for camera-opening coordination
_shared_camera_lock = threading.Lock()


class SharedCamera:
    """Thread-safe camera handle. Stores the cam object set by the grabbing thread."""
    def __init__(self):
        self._lock = threading.Lock()
        self._cam = None
        self._open = False

    @property
    def is_open(self) -> bool:
        with self._lock:
            return self._open

    def set_cam(self, cam):
        """Set the camera object (called from within 'with cams[0] as cam:')."""
        with self._lock:
            self._cam = cam
            self._open = True

    def close(self):
        """Mark camera as closed."""
        with self._lock:
            self._cam = None
            self._open = False


# Module-level shared camera handler — one per streaming session.
_shared_camera: Optional[SharedCamera] = None


def _camera_grabbing_loop(handler: SharedCamera) -> None:
    """Background thread: holds camera handle and updates _latest_frame.

    Uses asynchronous acquisition (start_streaming) with ring buffers to avoid
    the latency and transport-layer USB crashes of repeated synchronous get_frame() calls.
    All generators read the shared _latest_frame (protected by _frame_lock, via copy()).
    """
    global _grab_running, _last_camera_model, _last_camera_serial, _last_camera_detected
    global _latest_frame

    _grab_running = True
    logger.info("Camera grabbing thread started")

    try:
        if not _vmb_system_initialized:
            _init_vmb_system()

        from vmbpy import PersistType, FrameStatus

        for attempt in range(1, 20):
            if not _grab_running:
                logger.info("Grab thread: _grab_running=False, exiting")
                break
            try:
                if _vmb_system is None:
                    logger.debug(f"Grab thread attempt {attempt}/19: VmbSystem not ready, waiting...")
                    time.sleep(1.0)
                    continue
                cams = _vmb_system.get_all_cameras()
                if not cams:
                    logger.warning(f"Grab thread attempt {attempt}/19: No cameras found, retrying...")
                    time.sleep(1.0)
                    continue

                logger.info(f"Grab thread attempt {attempt}/19: found {len(cams)} camera(s), opening...")
                exposure = float(get_camera_setting("exposure") or 140.0)
                gain = float(get_camera_setting("gain") or 5.0)

                # ─── 'with' block held for streaming session ───
                with cams[0] as cam:
                    handler.set_cam(cam)

                    # Load cached camera settings
                    settings_file = '/home/Ento/LepmonOS/Kamera_Einstellungen_VimbaX.xml'
                    if os.path.exists(settings_file):
                        try:
                            cam.load_settings(settings_file, PersistType.All)
                            logger.info("Loaded camera settings from XML file")
                        except Exception as e:
                            logger.warning(f"Could not load camera settings: {e}")

                    try:
                        cam.ExposureTime.set(exposure * 1000)
                        cam.Gain.set(gain)
                    except Exception as e:
                        logger.warning(f"Could not set exposure/gain: {e}")

                    # Enable 2x2 binning to reduce USB transfer bandwidth by 75% on Raspberry Pi
                    try:
                        cam.BinningSelector.set("Digital")
                        cam.BinningHorizontal.set(2)
                        cam.BinningVertical.set(2)
                        logger.info("Grab thread: enabled 2x2 digital binning for web preview")
                    except Exception as e:
                        logger.debug(f"Could not configure binning (using sensor default): {e}")

                    # Limit hardware frame rate to ~4 FPS to avoid flooding USB3 FIFO
                    try:
                        cam.AcquisitionFrameRateEnable.set(True)
                        cam.AcquisitionFrameRate.set(4.0)
                        logger.info("Grab thread: set camera frame rate to 4.0 FPS")
                    except Exception as e:
                        logger.debug(f"Could not set AcquisitionFrameRate: {e}")

                    try:
                        model = cam.get_model()
                        serial = cam.get_serial()
                    except Exception:
                        model = "Unknown"
                        serial = "--"
                    _last_camera_model = model
                    _last_camera_serial = serial
                    _last_camera_detected = True
                    logger.info(f"Camera opened in grabbing thread: model={model}, serial={serial}")

                    frames_grabbed = 0
                    last_grab_time = 0.0
                    streaming_started = False
                    stream_broken = False

                    def frame_handler(cam_obj, stream_obj, frame_obj):
                        global _latest_frame
                        nonlocal last_grab_time, frames_grabbed
                        try:
                            status = frame_obj.get_status()
                            if status == FrameStatus.Complete:
                                now = time.time()
                                # Throttle image conversion to ~2.5 FPS for preview
                                if now - last_grab_time >= 0.35:
                                    raw = frame_obj.as_opencv_image()
                                    if raw is not None and raw.ndim >= 2 and raw.shape[0] > 10 and raw.shape[1] > 10:
                                        with _frame_lock:
                                            _latest_frame = raw
                                        last_grab_time = now
                                        frames_grabbed += 1
                                        if frames_grabbed == 1:
                                            logger.info(f"Grab thread: first frame captured ({raw.shape[1]}x{raw.shape[0]})")
                                        elif frames_grabbed % 50 == 0:
                                            logger.info(f"Grab thread: {frames_grabbed} frames captured so far")
                            else:
                                logger.warning(f"Grab thread: incomplete frame (status={status}), skipping")
                        except Exception as h_err:
                            logger.error(f"Error in grab thread frame handler: {h_err}")
                        finally:
                            try:
                                cam_obj.queue_frame(frame_obj)
                            except Exception:
                                pass

                    # Try asynchronous streaming first (preferred)
                    try:
                        cam.start_streaming(handler=frame_handler, buffer_count=5)
                        streaming_started = True
                        logger.info("Grab thread: asynchronous streaming started successfully")
                    except Exception as s_err:
                        logger.warning(f"Grab thread: start_streaming failed ({s_err}), falling back to get_frame()")
                        streaming_started = False

                    applied_exposure = exposure
                    applied_gain = gain
                    last_frame_count = 0
                    stuck_seconds = 0.0
                    sync_error_count = 0
                    auto_frame_count = 0  # Counter for auto exposure/gain
                    last_exposure_mode = "auto"  # Track mode transitions

                    while _grab_running and handler.is_open:
                        is_capturing = get_camera_state("is_capturing") or False
                        free_for_web = get_camera_state("free_for_web") or False
                        if is_capturing or not free_for_web:
                            logger.info(
                                f"Grabbing: camera busy or not free, stopping "
                                f"(is_capturing={is_capturing}, free_for_web={free_for_web}). "
                                f"Frames grabbed so far: {frames_grabbed}"
                            )
                            break

                        # Check exposure mode from web UI
                        curr_mode = get_camera_setting("_exposure_mode") or exposure_mode

                        # Detect mode transition → lock / unlock camera auto controls
                        if curr_mode != last_exposure_mode:
                            try:
                                if curr_mode == "manual":
                                    # Switching to manual: disable camera auto controls
                                    # so the manual values actually stick
                                    cam.ExposureAuto.set("Off")
                                    cam.GainAuto.set("Off")
                                    logger.info("Grab thread: switched to manual mode, disabled camera auto controls")
                                last_exposure_mode = curr_mode
                            except Exception as e:
                                logger.warning(f"Could not set camera auto controls: {e}")

                        if curr_mode == "auto":
                            # Auto mode: recalculate exposure/gain on frame 1 and every 10th frame
                            auto_frame_count += 1
                            if auto_frame_count == 1 or auto_frame_count % 10 == 0:
                                try:
                                    # Set continuous auto exposure for this frame
                                    cam.ExposureAuto.set("Continuous")
                                    cam.GainAuto.set("Continuous")
                                    time.sleep(0.05)  # Brief delay for camera to adjust
                                    
                                    # Get the auto-calculated values
                                    auto_exp = cam.ExposureTime.get() / 1000.0  # Convert from microseconds to ms
                                    auto_gain = cam.Gain.get()
                                    
                                    # Save to cache
                                    set_camera_setting("exposure", round(auto_exp, 1))
                                    set_camera_setting("gain", round(auto_gain, 1))
                                    
                                    logger.info(
                                        f"Grab thread: Auto exposure/gain - "
                                        f"exposure={auto_exp:.1f}ms, gain={auto_gain:.1f}dB"
                                    )
                                    
                                    # Apply the new values
                                    cam.ExposureTime.set(auto_exp * 1000)
                                    cam.Gain.set(auto_gain)
                                    applied_exposure = auto_exp
                                    applied_gain = auto_gain
                                except Exception as e:
                                    logger.warning(f"Auto exposure/gain failed: {e}")
                        else:
                            # Manual mode: use values from web UI
                            curr_exp = float(get_camera_setting("exposure") or 140.0)
                            curr_gain = float(get_camera_setting("gain") or 5.0)
                            if abs(curr_exp - applied_exposure) > 0.5:
                                try:
                                    cam.ExposureTime.set(curr_exp * 1000)
                                    applied_exposure = curr_exp
                                    logger.info(f"Grab thread: updated ExposureTime to {curr_exp} ms")
                                except Exception as e:
                                    logger.warning(f"Could not update ExposureTime: {e}")
                            if abs(curr_gain - applied_gain) > 0.2:
                                try:
                                    cam.Gain.set(curr_gain)
                                    applied_gain = curr_gain
                                    logger.info(f"Grab thread: updated Gain to {curr_gain}")
                                except Exception as e:
                                    logger.warning(f"Could not update Gain: {e}")

                        if streaming_started:
                            # Asynchronous mode: monitor that frames are actually arriving
                            time.sleep(0.5)
                            if frames_grabbed == last_frame_count:
                                stuck_seconds += 0.5
                                if stuck_seconds >= 5.0:
                                    logger.warning("Grab thread: no frames received for 5s, reconnecting camera...")
                                    stream_broken = True
                                    break
                            else:
                                stuck_seconds = 0.0
                                last_frame_count = frames_grabbed
                        else:
                            # Fallback synchronous mode with robust status check & error breaking
                            try:
                                frame_obj = cam.get_frame(timeout_ms=2500)
                                if frame_obj.get_status() == FrameStatus.Complete:
                                    raw = frame_obj.as_opencv_image()
                                    if raw is not None and raw.ndim >= 2 and raw.shape[0] > 10 and raw.shape[1] > 10:
                                        with _frame_lock:
                                            _latest_frame = raw
                                        frames_grabbed += 1
                                        sync_error_count = 0
                                        if frames_grabbed == 1:
                                            logger.info(f"Grab thread: first frame captured ({raw.shape[1]}x{raw.shape[0]})")
                                        elif frames_grabbed % 50 == 0:
                                            logger.info(f"Grab thread: {frames_grabbed} frames captured so far")
                                else:
                                    logger.warning(f"Grab thread: incomplete frame (status={frame_obj.get_status()}), skipping")
                            except Exception as e:
                                sync_error_count += 1
                                logger.error(f"Grab error in thread ({sync_error_count}/3): {e}")
                                if sync_error_count >= 3:
                                    logger.warning("Grab thread: 3 consecutive grab errors, reconnecting camera...")
                                    stream_broken = True
                                    break
                            time.sleep(0.5)

                    # Stop streaming cleanly if it was started
                    if streaming_started:
                        try:
                            cam.stop_streaming()
                            logger.info("Grab thread: asynchronous streaming stopped")
                        except Exception as e:
                            logger.warning(f"Grab thread: error stopping stream: {e}")

                    # If stream broke while running and we should still be running, retry by continuing outer loop
                    if stream_broken and _grab_running and handler.is_open:
                        logger.info("Grab thread: restarting camera session after stream failure...")
                        time.sleep(1.0)
                        continue

                break  # Success / normal exit: leave retry loop
            except Exception as e:
                logger.warning(f"Grab thread open attempt {attempt}/19 failed: {e}")
                time.sleep(min(1.0, attempt * 0.2))

        else:
            # Loop exhausted all 19 attempts without breaking (camera never opened)
            logger.error("Grab thread: all 19 attempts failed — camera never opened")

    except Exception as e:
        logger.error(f"Camera grabbing thread crashed: {e}")
    finally:
        _grab_running = False
        handler.close()
        logger.info("Camera grabbing thread stopped")


# ─── Shared RPI Camera Handler + Background Grabbing Thread ──────────────────
# picamera2 allows capture_array() from the same thread that started the camera.
# A dedicated background thread holds the Picamera2 instance for the entire
# streaming session. It grabs frames and stores them in _latest_frame_rpi
# (protected by _rpi_frame_lock). All MJPEG generators read this shared
# frame via .copy(), so no queue contention occurs.
_latest_frame_rpi: Optional[np.ndarray] = None
_rpi_frame_lock = threading.Lock()

# Background grabbing thread state for RPI
_rpi_grab_thread: Optional[threading.Thread] = None
_rpi_grab_running = False

# Lock for RPI camera-opening coordination
_rpi_shared_camera_lock = threading.Lock()


class SharedRPICamera:
    """Thread-safe RPI camera handle. Stores the Picamera2 object."""
    def __init__(self):
        self._lock = threading.Lock()
        self._cam = None
        self._open = False

    @property
    def is_open(self) -> bool:
        with self._lock:
            return self._open

    @property
    def cam(self):
        with self._lock:
            return self._cam

    def set_cam(self, cam):
        with self._lock:
            self._cam = cam
            self._open = True

    def close(self):
        """Stop and close the Picamera2 camera."""
        with self._lock:
            if self._cam is not None:
                try:
                    self._cam.stop()
                    self._cam.close()
                except Exception as e:
                    logger.warning(f"Error closing RPI camera: {e}")
                self._cam = None
            self._open = False


# Module-level shared RPI camera handler — one per streaming session.
_rpi_shared_camera: Optional[SharedRPICamera] = None


def _rpi_grabbing_loop(handler: SharedRPICamera) -> None:
    """Background thread: holds Picamera2 instance and updates _latest_frame_rpi."""
    global _rpi_grab_running, _last_camera_model, _last_camera_detected
    global _latest_frame_rpi

    _rpi_grab_running = True
    logger.info("RPI camera grabbing thread started")

    picam2 = None
    try:
        # Read camera settings from config
        exposure_gain = get_value_from_section(
            "/home/Ento/LepmonOS/Lepmon_config.json", "RPI_Module_3", "initial_exposure_10"
        )
        gain_val = get_value_from_section(
            "/home/Ento/LepmonOS/Lepmon_config.json", "RPI_Module_3", "initial_gain_10"
        )
        compression_quality = get_value_from_section(
            "/home/Ento/LepmonOS/Lepmon_config.json", "RPI_Module_3", "compression_quality"
        )
        if exposure_gain is None:
            exposure_gain = 20
        if gain_val is None:
            gain_val = 20
        if compression_quality is None:
            compression_quality = 90

        Exposure = int(exposure_gain) / 10
        Gain = int(gain_val) / 10

        for attempt in range(1, 10):
            if not _rpi_grab_running:
                logger.info("RPI grab thread: _rpi_grab_running=False, exiting")
                break
            try:
                logger.info(f"RPI grab thread attempt {attempt}/10: opening Picamera2...")
                try:
                    picam2 = Picamera2(0)
                except Exception:
                    picam2 = Picamera2()
                preview_config = picam2.create_preview_configuration(
                    main={"size": (1920, 1080)}
                )
                picam2.configure(preview_config)
                picam2.start()
                picam2.set_controls({
                    "AnalogueGain": Gain,
                    "ExposureTime": int(Exposure * 1000),
                })
                handler.set_cam(picam2)

                _last_camera_model = "Raspberry Pi Camera Module 3"
                _last_camera_detected = True
                logger.info("RPI Camera opened in grabbing thread")

                # ─── Frame grabbing loop ───
                frames_grabbed = 0
                auto_frame_count = 0  # Counter for auto exposure/gain
                applied_exposure = Exposure
                applied_gain = Gain
                last_exposure_mode = "auto"  # Track mode transitions
                last_focus_mode = get_camera_setting("focus_mode") or "manual"
                applied_focus = 5.3  # default lens position
                while _rpi_grab_running and handler.is_open:
                    is_capturing = get_camera_state("is_capturing") or False
                    free_for_web = get_camera_state("free_for_web") or False
                    if is_capturing or not free_for_web:
                        logger.info(
                            f"RPI grabbing: camera busy or not free, stopping "
                            f"(is_capturing={is_capturing}, free_for_web={free_for_web}). "
                            f"Frames grabbed so far: {frames_grabbed}"
                        )
                        break
                    
                    # Check exposure mode from web UI
                    curr_mode = get_camera_setting("_exposure_mode") or exposure_mode

                    # Detect mode transition → lock / unlock camera auto controls
                    if curr_mode != last_exposure_mode:
                        if curr_mode == "manual":
                            # Switching to manual: disable camera auto controls
                            # so the manual values actually stick.
                            # Set each control individually — some cameras (e.g. RPI
                            # Module 3) don't advertise AgEnable and would fail with a
                            # combined set_controls() call.
                            for ctrl_name, ctrl_val in [("AeEnable", False), ("AgEnable", False)]:
                                try:
                                    picam2.set_controls({ctrl_name: ctrl_val})
                                except Exception:
                                    pass  # Control not advertised — ignore
                            logger.info("RPI grab thread: switched to manual mode, disabled camera auto controls")
                        last_exposure_mode = curr_mode

                    if curr_mode == "auto":
                        # Auto mode: recalculate exposure/gain on frame 1 and every 10th frame
                        auto_frame_count += 1
                        if auto_frame_count == 1 or auto_frame_count % 10 == 0:
                            try:
                                # Enable auto exposure/gain for this frame.
                                # Set each control individually — some cameras don't
                                # advertise AgEnable and would fail with a combined call.
                                for ctrl_name, ctrl_val in [("AeEnable", True), ("AgEnable", True)]:
                                    try:
                                        picam2.set_controls({ctrl_name: ctrl_val})
                                    except Exception:
                                        pass  # Control not advertised — ignore
                                time.sleep(0.05)  # Brief delay for camera to adjust
                                
                                # Get the auto-calculated values from camera metadata
                                metadata = picam2.capture_metadata("main")
                                auto_exp = metadata.get("ExposureTime", int(Exposure * 1000)) / 1000.0
                                auto_gain = metadata.get("AnalogueGain", Gain)
                                
                                # Save to cache
                                set_camera_setting("exposure", round(auto_exp, 1))
                                set_camera_setting("gain", round(auto_gain, 1))
                                
                                logger.info(
                                    f"RPI grab thread: Auto exposure/gain - "
                                    f"exposure={auto_exp:.1f}ms, gain={auto_gain:.1f}dB"
                                )
                                
                                # Apply the new values
                                picam2.set_controls({
                                    "ExposureTime": int(auto_exp * 1000),
                                    "AnalogueGain": auto_gain,
                                })
                                applied_exposure = auto_exp
                                applied_gain = auto_gain
                            except Exception as e:
                                logger.warning(f"RPI auto exposure/gain failed: {e}")
                    else:
                        # Manual mode: use values from web UI
                        curr_exp = float(get_camera_setting("exposure") or Exposure)
                        curr_gain = float(get_camera_setting("gain") or Gain)
                        if abs(curr_exp - applied_exposure) > 0.5 or abs(curr_gain - applied_gain) > 0.2:
                            try:
                                picam2.set_controls({
                                    "ExposureTime": int(curr_exp * 1000),
                                    "AnalogueGain": curr_gain,
                                })
                                applied_exposure = curr_exp
                                applied_gain = curr_gain
                                logger.info(f"RPI grab thread: updated Exposure={curr_exp}ms, Gain={curr_gain}dB")
                            except Exception as e:
                                logger.warning(f"RPI could not update exposure/gain: {e}")

                    # ── Focus mode handling (auto/manual lens position) ──
                    curr_focus_mode = get_camera_setting("focus_mode") or "manual"
                    if curr_focus_mode != last_focus_mode:
                        try:
                            if curr_focus_mode == "auto":
                                picam2.set_controls({
                                    "AfMode": controls.AfModeEnum.Continuous
                                })
                                logger.info("RPI grab thread: focus -> auto (continuous)")
                            else:
                                picam2.set_controls({
                                    "AfMode": controls.AfModeEnum.Manual,
                                    "LensPosition": applied_focus,
                                })
                                logger.info(f"RPI grab thread: focus -> manual, locked LensPosition={applied_focus:.2f}")
                            last_focus_mode = curr_focus_mode
                        except Exception as e:
                            logger.warning(f"RPI could not set focus mode: {e}")

                    if curr_focus_mode == "auto":
                        if auto_frame_count % 10 == 0:
                            try:
                                meta = picam2.capture_metadata("main")
                                auto_lens = meta.get("LensPosition", applied_focus)
                                set_camera_setting("lens_position", round(auto_lens, 2))
                                applied_focus = auto_lens
                                logger.info(f"RPI grab thread: auto focus LensPosition={auto_lens:.2f}")
                            except Exception as e:
                                logger.warning(f"RPI read lens position failed: {e}")
                    else:
                        # Manual mode: read focus_diopter and convert to lens position.
                        # Diopter range: -15 (macro) .. 1 (infinity)
                        # Lens position range: 0.0 (macro) .. 10.0 (infinity)
                        curr_diopter = float(get_camera_setting("focus_diopter") or -8)
                        curr_focus = max(0.0, min(10.0, (curr_diopter + 15) / 16 * 10))
                        if abs(curr_focus - applied_focus) > 0.1:
                            try:
                                picam2.set_controls({
                                    "AfMode": controls.AfModeEnum.Manual,
                                    "LensPosition": curr_focus,
                                })
                                applied_focus = curr_focus
                                logger.info(f"RPI grab thread: manual LensPosition={curr_focus:.2f} (diopter={curr_diopter:.1f})")
                            except Exception as e:
                                logger.warning(f"RPI update lens position failed: {e}")

                    try:
                        raw = picam2.capture_array("main")
                        if raw.ndim == 3 and raw.shape[2] == 4:
                            raw = cv2.cvtColor(raw, cv2.COLOR_BGRA2BGR)   
                        with _rpi_frame_lock:
                            _latest_frame_rpi = raw       
                        frames_grabbed += 1
                        if frames_grabbed == 1:
                            logger.info(f"RPI grab thread: first frame captured ({raw.shape[1]}x{raw.shape[0]})")
                        elif frames_grabbed % 50 == 0:
                            logger.info(f"RPI grab thread: {frames_grabbed} frames captured so far")
                    except Exception as e:
                        logger.error(f"RPI grab error in thread (frame #{frames_grabbed + 1}): {e}")
                        time.sleep(0.2)
                    time.sleep(0.1)  # ~10 FPS grab rate
                break  # Success: leave retry loop

            except Exception as e:
                logger.warning(f"RPI grab thread open attempt {attempt}/10 failed: {e}")
                if picam2 is not None:
                    try:
                        picam2.stop()
                        picam2.close()
                    except Exception:
                        pass
                    picam2 = None
                time.sleep(min(1.0, attempt * 0.2))
        else:
            logger.error("RPI grab thread: all 10 attempts failed — camera never opened")

    except Exception as e:
        logger.error(f"RPI camera grabbing thread crashed: {e}")
    finally:
        _rpi_grab_running = False
        handler.close()
        logger.info("RPI camera grabbing thread stopped")


def _capture_rpi_snapshot() -> Optional[np.ndarray]:
    """Open a short-lived Picamera2 session, grab one frame, and close.

    Used by the /snapshot endpoint so the snapshot works even when the
    streaming thread is not running (i.e. _latest_frame_rpi is None).
    """
    # Read camera settings from config
    exposure_gain = get_value_from_section(
        "/home/Ento/LepmonOS/Lepmon_config.json", "RPI_Module_3", "initial_exposure_10"
    )
    gain_val = get_value_from_section(
        "/home/Ento/LepmonOS/Lepmon_config.json", "RPI_Module_3", "initial_gain_10"
    )
    if exposure_gain is None:
        exposure_gain = 20
    if gain_val is None:
        gain_val = 20

    Exposure = int(exposure_gain) / 10
    Gain = int(gain_val) / 10

    picam2 = None
    try:
        try:
            picam2 = Picamera2(0)
        except Exception:
            picam2 = Picamera2()
        preview_config = picam2.create_preview_configuration(
            main={"size": (1920, 1080)}
        )
        picam2.configure(preview_config)
        picam2.start()
        picam2.set_controls({
            "AnalogueGain": Gain,
            "ExposureTime": int(Exposure * 1000),
        })

        # Wait briefly for the camera to stabilise
        time.sleep(0.3)

        raw = picam2.capture_array("main")
        if raw.ndim == 3 and raw.shape[2] == 4:
            raw = cv2.cvtColor(raw, cv2.COLOR_BGRA2BGR)
        logger.info(f"RPI snapshot captured ({raw.shape[1]}x{raw.shape[0]})")
        return raw

    except Exception as e:
        logger.error(f"RPI snapshot failed: {e}")
        return None

    finally:
        if picam2 is not None:
            try:
                picam2.stop()
                picam2.close()
            except Exception:
                pass


def _capture_av_snapshot() -> Optional[np.ndarray]:
    """Capture a full-resolution AV snapshot by briefly pausing the stream.

    The streaming grab thread uses 2x2 binning (1/4 resolution) and does not
    allow changing camera settings while streaming. Therefore this function:
      1. Checks whether the grab thread is running
      2. Stops it briefly
      3. Captures a frame at full sensor resolution (no binning)
      4. Restarts the grab thread (if it was running)
    """
    global _grab_running, _grab_thread, _latest_frame
    try:
        from vmbpy import PersistType, FrameStatus

        if _vmb_system is None:
            logger.error("VmbSystem not initialized for AV snapshot")
            return None

        cams = _vmb_system.get_all_cameras()
        if not cams:
            logger.warning("No AV camera found for snapshot")
            return None

        exposure = int(get_camera_setting("exposure") or 140)
        gain = float(get_camera_setting("gain") or 5.0)

        # Check if the grab thread is running
        was_running = _grab_running and _grab_thread is not None and _grab_thread.is_alive()
        snapshot_frame = None

        if was_running:
            # Stop the grab thread so the camera is available for direct access
            logger.info("AV snapshot: pausing stream grab thread...")
            _grab_running = False
            _grab_thread.join(timeout=3.0)

        # Now capture a frame at full resolution (no binning)
        try:
            with cams[0] as cam:
                # Load persisted settings
                settings_file = "/home/Ento/LepmonOS/Kamera_Einstellungen_VimbaX.xml"
                if os.path.exists(settings_file):
                    try:
                        cam.load_settings(settings_file, PersistType.All)
                    except Exception as e:
                        logger.warning(f"Could not load camera settings for snapshot: {e}")

                # Ensure binning is disabled (1x1 = full sensor resolution)
                try:
                    cam.BinningHorizontal.set(1)
                    cam.BinningVertical.set(1)
                    logger.info("AV snapshot: binning set to 1x1 (full resolution)")
                except Exception as e:
                    logger.warning(f"Could not set binning for snapshot: {e}")

                # Set exposure and gain
                try:
                    cam.ExposureTime.set(exposure * 1000)
                    cam.Gain.set(gain)
                except Exception as e:
                    logger.warning(f"Could not set exposure/gain for snapshot: {e}")

                # Capture frame
                frame_obj = cam.get_frame(timeout_ms=5000)
                if frame_obj.get_status() == FrameStatus.Complete:
                    snapshot_frame = frame_obj.as_opencv_image()
                    logger.info(f"AV snapshot captured ({snapshot_frame.shape[1]}x{snapshot_frame.shape[0]})")
                else:
                    logger.warning(f"AV snapshot: incomplete frame (status={frame_obj.get_status()})")
        finally:
            if was_running:
                # Restart the grab thread
                logger.info("AV snapshot: restarting stream grab thread...")
                # Re-initialize the shared camera for the grab thread
                with _shared_camera_lock:
                    if _shared_camera is not None:
                        _shared_camera.close()
                        _shared_camera = None
                    _shared_camera = SharedCamera()
                    _latest_frame = None
                _grab_thread = threading.Thread(
                    target=_camera_grabbing_loop,
                    args=(_shared_camera,),
                    daemon=True,
                )
                _grab_running = True
                _grab_thread.start()
                logger.info("AV snapshot: grab thread restarted")

        return snapshot_frame

    except ImportError:
        logger.error("VmbPy SDK not available for AV snapshot")
        return None
    except Exception as e:
        logger.error(f"AV snapshot failed: {e}")
        # Ensure the grab thread is restarted if it was running
        try:
            global_was_running = _grab_thread is not None and _grab_thread.is_alive()
            if global_was_running:
                logger.warning("AV snapshot: attempt to recover grab thread after error")
                with _shared_camera_lock:
                    if _shared_camera is not None:
                        _shared_camera.close()
                        _shared_camera = None
                    _shared_camera = SharedCamera()
                    _latest_frame = None
                _grab_thread = threading.Thread(
                    target=_camera_grabbing_loop,
                    args=(_shared_camera,),
                    daemon=True,
                )
                _grab_running = True
                _grab_thread.start()
        except Exception as recovery_err:
            logger.error(f"AV snapshot: failed to recover grab thread: {recovery_err}")
        return None


# ── Camera state cache is in json_read_write.py (shared with Camera_AV.py) ──
# Import get_camera_state / set_camera_state from json_read_write

# ── VmbSystem singleton (lazy init, only when web_requested = true) ──
# VmbSystem is a true singleton. Each 'with' block's __exit__() tears down
# the entire SDK, which breaks streams and causes "System not ready" errors
# when another thread is still using it.
#
# CRITICAL: We do NOT initialize VmbSystem at module load because lepmon-main
# (Camera_AV.py) uses the same SDK. Two processes sharing vmbpy causes
# BadHandle / BadParameter errors. Instead we initialize lazily ONLY when
# web_requested becomes true (meaning the user explicitly asked for web stream).
# When web_requested goes back to false, we shut down to release the SDK for
# lepmon-main to use again.

_vmb_system = None
_vmb_system_initialized = False


def _init_vmb_system() -> bool:
    """Lazily initialize VmbSystem. Returns True on success.

    Only called when web_requested transitions to true.
    If already initialized, returns True immediately.
    """
    global _vmb_system, _vmb_system_initialized
    if _vmb_system_initialized:
        return True
    try:
        from vmbpy import VmbSystem as _VmbSystemInit  # noqa: PLC0415
        _vmb_system = _VmbSystemInit.get_instance()
        _vmb_system.__enter__()
        _vmb_system_initialized = True
        logger.info("VmbSystem initialized on demand (web_requested = true)")
        return True
    except Exception as e:
        logger.warning(f"VmbSystem init failed (will retry on next frame): {e}")
        return False


def _shutdown_vmb_system() -> None:
    """Shut down VmbSystem to release the SDK for lepmon-main.

    Called when web_requested transitions to false.
    """
    global _vmb_system, _vmb_system_initialized
    if not _vmb_system_initialized:
        return
    try:
        _vmb_system.__exit__(None, None, None)
        logger.info("VmbSystem shut down (web_requested = false, SDK released)")
    except Exception as e:
        logger.warning(f"VmbSystem shutdown failed: {e}")
    _vmb_system = None
    _vmb_system_initialized = False
# All camera settings live here. The file is read ONCE at startup as a fallback,
# but all runtime reads/writes go through this dict (thread-safe via camera_lock).
# This eliminates the permission-denied issue and also speeds up the streaming
# loop which previously re-read JSON on every frame (~5 FPS).

_CAMERA_SETTINGS = {
    "exposure": 140.0,    # ms  (1–10000)
    "gain": 5.0,          # dB  (0–48)
    "downscale": 8,       # int (1–20)
    "zoom": 2,            # int (1–5)
    "_exposure_mode": "auto",  # auto or manual
    "focus_mode": "manual",    # auto or manual (for lens position / autofocus)
    "lens_position": 5.3,      # current lens position read from camera (auto mode)
    "focus_diopter_pos": 5.3,  # legacy: manual lens position 0.0 (infinity) – 10.0 (macro)
    "focus_diopter": -8.0,     # primary focus control in diopters: -15 (macro) .. 1 (infinity)
}

def _load_camera_settings_from_file() -> dict:
    """Try to load camera settings from Lepmon_config.json. Returns defaults on any error."""
    settings = dict(_CAMERA_SETTINGS)  # start with defaults
    try:
        val = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "Camera_Stream", "exposure")
        if isinstance(val, (int, float)):
            settings["exposure"] = float(val)
        val = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "Camera_Stream", "gain")
        if isinstance(val, (int, float)):
            settings["gain"] = float(val)
        val = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "Camera_Stream", "downscale")
        if isinstance(val, (int, float)):
            settings["downscale"] = int(val)
        val = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "Camera_Stream", "zoom")
        if isinstance(val, (int, float)):
            settings["zoom"] = int(val)
        logger.info(f"Loaded camera settings from config: {settings}")
    except Exception as e:
        logger.warning(f"Could not load camera settings from config, using defaults: {e}")
    return settings

# Populate the cache at module load time
_CAMERA_SETTINGS.update(_load_camera_settings_from_file())
logger.info(f"Camera settings cache initialized: {_CAMERA_SETTINGS}")

# -----------------------------------------------------------------------------
# Convenience helpers (used throughout the file)
# -----------------------------------------------------------------------------

def get_camera_setting(key: str):
    """Read a camera setting from the in-memory cache (thread-safe)."""
    with camera_lock:
        return _CAMERA_SETTINGS.get(key)

def set_camera_setting(key: str, value):
    """Write a camera setting into the in-memory cache (thread-safe)."""
    with camera_lock:
        _CAMERA_SETTINGS[key] = value

# Legacy aliases for backward compatibility with existing code references
DEFAULT_EXPOSURE = _CAMERA_SETTINGS["exposure"]
DEFAULT_GAIN = _CAMERA_SETTINGS["gain"]
STREAM_DOWNSCALE = _CAMERA_SETTINGS["downscale"]
STREAM_ZOOM = _CAMERA_SETTINGS["zoom"]


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
    """Background thread: poll camera presence every 2s and update in-memory cache.

    Uses the module-level _vmb_system singleton directly — no 'with' blocks
    that would tear down the SDK while the streaming thread is using it.

    The detection result is written to the in-memory cache, NOT to the JSON
    file, to avoid Permission denied errors.
    """
    while True:
        detected = False
        try:
            if _vmb_system is not None:
                cams = _vmb_system.get_all_cameras()
                detected = bool(cams)
                logger.debug(f"Camera detection poll: found {len(cams) if cams else 0} camera(s)")
        except ImportError:
            logger.debug("vmbpy not available for camera detection polling")
        except Exception as e:
            logger.debug(f"Camera detection poll failed: {e}")

        # Write to in-memory cache instead of JSON file (avoids Permission denied)
        set_camera_state("is_detected", detected)

        time.sleep(5)


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


# ---------- Camera state sync from JSON (for cross-process visibility) ----------

# Keys written by other processes (trap_hmi.py, Camera_AV.py) that we must
# re-read from the JSON file periodically.  'is_detected' is excluded because
# the polling thread owns that key.
_CAMERA_STATE_SYNC_KEYS = [
    "has_power",
    "is_capturing",
    "free_for_web",
    "web_requested",
    "web_focus_active",
]

_sync_running = True


def _sync_camera_state_from_file() -> None:
    """Background thread: re-read Camera_state from JSON every 5 seconds.

    Other programs (trap_hmi.py, Camera_AV.py) write to the JSON file directly.
    This thread keeps the in-memory cache in sync with those external writes.

    'is_detected' is NOT synced here — it is owned by the polling thread.

    Transition handling:
      - has_power True → False  : clear cached camera info
      - web_requested False → True : initialize VmbSystem (lazy)
      - web_requested True → False : shutdown VmbSystem (release SDK for lepmon-main)
    """
    global _sync_running, _last_camera_model, _last_camera_serial, _last_camera_detected
    prev_has_power = get_camera_state("has_power")
    prev_web_requested = get_camera_state("web_requested")

    while _sync_running:
        try:
            with open("/home/Ento/LepmonOS/Lepmon_config.json", "r") as f:
                data = json.load(f)
            state = data.get("Camera_state", {})

            for key in _CAMERA_STATE_SYNC_KEYS:
                val = state.get(key)
                if isinstance(val, bool):
                    set_camera_state(key, val)

            # --- Transition: has_power True → False ---
            new_has_power = get_camera_state("has_power")
            if prev_has_power is True and new_has_power is False:
                logger.info("has_power turned off — clearing cached camera info")
                _last_camera_model = None
                _last_camera_serial = None
                _last_camera_detected = False
            prev_has_power = new_has_power

            # --- Transition: web_requested False → True (init VmbSystem) ---
            new_web_requested = get_camera_state("web_requested")
            if prev_web_requested is False and new_web_requested is True:
                logger.info("web_requested turned on — initializing VmbSystem")
                _init_vmb_system()
            # --- Transition: web_requested True → False (shutdown VmbSystem) ---
            elif prev_web_requested is True and new_web_requested is False:
                logger.info("web_requested turned off — shutting down VmbSystem")
                _shutdown_vmb_system()
            prev_web_requested = new_web_requested

        except Exception as e:
            logger.debug(f"Camera state sync failed: {e}")

        time.sleep(5)


def _start_camera_state_sync() -> None:
    """Launch the camera state JSON-sync background thread."""
    global _camera_sync_thread
    if _camera_sync_thread is not None and _camera_sync_thread.is_alive():
        return
    _camera_sync_thread = threading.Thread(
        target=_sync_camera_state_from_file, daemon=True
    )
    _camera_sync_thread.start()
    logger.info("Camera state sync thread started")


def _stop_camera_state_sync() -> None:
    """Signal the sync thread to stop."""
    global _sync_running
    _sync_running = False
    global _camera_sync_thread
    _camera_sync_thread = None
    logger.info("Camera state sync thread stopped")


def _check_camera_release_loop() -> None:
    """Periodic check (every 5s): if free_for_web is False, release camera for capturing."""
    while True:
        time.sleep(5)
        free_for_web = get_camera_state("free_for_web")
        if free_for_web == False:
            logger.info("free_for_web is False -> forcing camera release for capturing...")
            
            # Release AV camera
            with stream_consumers_lock:
                global _grab_thread, _grab_running
                if _grab_thread is not None and _grab_thread.is_alive() or _grab_running:
                    _grab_running = False
                    if _grab_thread is not None and _grab_thread.is_alive():
                        _grab_thread.join(timeout=3.0)
                    _grab_thread = None
                    with _shared_camera_lock:
                        if _shared_camera is not None:
                            _shared_camera.close()
                            _shared_camera = None
                        _latest_frame = None
                    streaming_active = False
                    stream_consumers = 0
            
            # Release RPI camera
            with stream_consumers_lock:
                global _rpi_grab_thread, _rpi_grab_running
                if _rpi_grab_thread is not None and _rpi_grab_thread.is_alive() or _rpi_grab_running:
                    _rpi_grab_running = False
                    if _rpi_grab_thread is not None and _rpi_grab_thread.is_alive():
                        _rpi_grab_thread.join(timeout=3.0)
                    _rpi_grab_thread = None
                    with _rpi_shared_camera_lock:
                        if _rpi_shared_camera is not None:
                            _rpi_shared_camera.close()
                            _rpi_shared_camera = None
                        _latest_frame_rpi = None
                    streaming_active = False
                    stream_consumers = 0
            
            logger.info("Camera(s) successfully released for capturing.")


def _start_camera_release_monitor() -> None:
    """Launch the camera release monitor background thread."""
    monitor_thread = threading.Thread(
        target=_check_camera_release_loop, daemon=True
    )
    monitor_thread.start()
    logger.info("Camera release monitor thread started")


_camera_sync_thread: Optional[threading.Thread] = None



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




def _dev_mode_frame() -> np.ndarray:
    note_mock("Allied Vision camera (vmbpy) for web streaming")
    return generate_mock_frame(640, 480, label="DEV MODE - stream")


def get_vimba_frame(exposure: int = DEFAULT_EXPOSURE, gain: float = DEFAULT_GAIN) -> Optional[np.ndarray]:
    """
    Capture a single frame from the Allied Vision camera using VmbPy SDK.
    Returns the frame as a numpy array, a DEV_MODE mock frame if no camera is
    found and DEV_MODE is on, or None if capture fails.

    If streaming is active, tries to reuse the SharedCamera to avoid
    "camera already in use" conflicts.
    """
    try:
        from vmbpy import PixelFormat, PersistType, FrameStatus

        # If streaming is active, try to grab from the shared latest frame
        if streaming_active:
            with _frame_lock:
                if _latest_frame is not None:
                    return _latest_frame.copy()

        if _vmb_system is None:
            logger.error("VmbSystem not initialized")
            return _dev_mode_frame() if DEV_MODE else None

        cams = _vmb_system.get_all_cameras()
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
            frame_obj = cam.get_frame(timeout_ms=5000)
            if frame_obj.get_status() == FrameStatus.Complete:
                frame = frame_obj.as_opencv_image()
                return frame
            else:
                logger.warning(f"get_vimba_frame: incomplete frame (status={frame_obj.get_status()})")
                return None

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


def frame_generator_AV() -> Generator[bytes, None, None]:
    """MJPEG stream generator — reads shared _latest_frame from background thread."""
    global current_frame, streaming_active, stream_consumers, _shared_camera
    global _latest_frame, _grab_thread, _grab_running

    #Frame modification parameters
    target_width = 1080
    text_scale = 1.2
    text_thickness = 2
    text_area_height = 160 # Schwarzer Informationsbereich: 1080 x 160 Pixel

    with stream_consumers_lock:
        stream_consumers += 1
        streaming_active = True

    logger.info(f"Stream consumer connected. Total consumers: {stream_consumers}")

    # Get or create shared handler + start grabbing thread
    with _shared_camera_lock:
        handler = _shared_camera
        if handler is None:
            handler = SharedCamera()
            _shared_camera = handler
            _latest_frame = None
            _grab_thread = threading.Thread(
                target=_camera_grabbing_loop, args=(handler,), daemon=True
            )
            _grab_thread.start()
            logger.info("Started camera grabbing background thread")

    # Wait for camera to be ready (up to 30s)
    logger.info("Waiting for camera to be ready...")
    for wait_i in range(30):
        if handler.is_open:
            break
        time.sleep(1.0)
    logger.info(f"Camera ready status after waiting 30 s: {handler.is_open}")

    if not handler.is_open:
        connecting = create_status_frame("Camera not available")
        _, jpeg = cv2.imencode(".jpg", connecting, [cv2.IMWRITE_JPEG_QUALITY, 80])
        yield (b"--frame\r\n" b"Content-Type: image/jpeg\r\n\r\n" + jpeg.tobytes() + b"\r\n")
        return

    try:
        local_frame_count = 0
        prev_zoom = None  # Track zoom changes for debug logging
        waiting_count = 0  # Track how many "waiting" frames we've yielded
        got_first_real = False  # Track transition from waiting → real frame
        while True:
            try:
                is_capturing = get_camera_state("is_capturing") or False
                free_for_web = get_camera_state("free_for_web") or False
                if is_capturing or not free_for_web:
                    logger.info("Stream: camera busy or not free for web — exiting generator")
                    return

                # Re-read downscale/zoom every frame so slider changes take effect immediately
                zoom = get_camera_setting("zoom") or 2
                downscale = get_camera_setting("downscale") or 8
                if zoom != prev_zoom:
                    logger.info(f"Stream frame generator: zoom={zoom}, downscale={downscale}")
                    prev_zoom = zoom

                # Read latest frame (shared across all consumers, each copies it)
                frame = None
                with _frame_lock:
                    if _latest_frame is not None:
                        frame = _latest_frame.copy()
                if frame is None or frame.ndim < 2 or frame.shape[0] < 10 or frame.shape[1] < 10:
                    # Wait briefly for the next frame rather than spamming placeholders
                    time.sleep(0.0125)
                    waiting_count += 1
                    if waiting_count == 1 or waiting_count % 10 == 0:
                        logger.info(
                            f"Stream generator: no valid frame available yet, "
                            f"yielding 'Waiting for camera' (attempt #{waiting_count})"
                        )
                    connecting = create_status_frame("Waiting for camera")
                    _, jpeg = cv2.imencode(".jpg", connecting, [cv2.IMWRITE_JPEG_QUALITY, 80])
                    yield (b"--frame\r\n" b"Content-Type: image/jpeg\r\n\r\n" + jpeg.tobytes() + b"\r\n")
                    time.sleep(0.125)
                    continue

                local_frame_count += 1
                if not got_first_real:
                    logger.info(
                        f"Stream generator: FIRST real frame received after {waiting_count} waiting attempts "
                        f"({frame.shape[1]}x{frame.shape[0]})"
                    )
                    got_first_real = True

                # Calculate and overlay metrics (use pre-downscale frame for accuracy)
                focus_score = calculate_focus_score(frame)
                brightness = calculate_brightness(frame)

                # 1) Center-crop zoom first (before downscale, for accuracy)
                if zoom > 1:
                    h, w = frame.shape[:2]
                    crop_h = max(1, int(h // zoom))
                    crop_w = max(1, int(w // zoom))
                    y_start = max(0, int((h - crop_h) // 2))
                    x_start = max(0, int((w - crop_w) // 2))
                    frame = frame[y_start:y_start + crop_h, x_start:x_start + crop_w]

                # 2) Downscale to reduce processing time and bandwidth
                h, w = frame.shape[:2]
                if downscale > 1:
                    new_w = max(1, int(w // downscale))
                    new_h = max(1, int(h // downscale))
                    frame = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)

                # Apply min/max stretch for better visibility
                stretched = apply_min_max_stretch(frame)

                # Resize for streaming with target width of 1080 px width
                h, w = stretched.shape[:2]

                if w != target_width:
                    scale = target_width / w
                    new_height = max(1, int(h * scale))

                    interpolation = (cv2.INTER_AREA
                        if w > target_width
                        else cv2.INTER_LINEAR)

                    stretched = cv2.resize(stretched, (target_width, new_height), interpolation=interpolation)


                image_height = stretched.shape[0] # Höhe des eigentlichen Bildes merken

                # Add information area below the image
                text_area = np.zeros(
                (text_area_height, target_width, 3), dtype=stretched.dtype)
                stretched = np.vstack((stretched, text_area))

                # Spaltenpositionen
                col1_x = 1
                col2_x = 361
                col3_x = 721

                cv2.putText(stretched,
                    f"Height: {h}",(col1_x, image_height + 32),
                    cv2.FONT_HERSHEY_SIMPLEX, text_scale, (255, 255, 255), text_thickness, cv2.LINE_AA)

                cv2.putText(stretched,
                    f"Width: {w}", (col2_x, image_height + 32),
                    cv2.FONT_HERSHEY_SIMPLEX, text_scale, (255, 255, 255), text_thickness, cv2.LINE_AA)

                cv2.putText(stretched,
                    f"Frame: {local_frame_count}", (col3_x, image_height + 32),
                    cv2.FONT_HERSHEY_SIMPLEX, text_scale, (255, 255, 255), text_thickness, cv2.LINE_AA)


                cv2.line(stretched, (1, image_height + 53), (1079, image_height + 53), (255, 255, 255), 1, cv2.LINE_AA)

                cv2.putText(stretched,
                    f"Zoom: {zoom:.1f}", (col1_x, image_height + 90),
                    cv2.FONT_HERSHEY_SIMPLEX, text_scale, (255, 255, 255), text_thickness, cv2.LINE_AA)

                cv2.putText(stretched,
                    f"Downscale: {downscale:.1f}", (col2_x, image_height + 90),
                    cv2.FONT_HERSHEY_SIMPLEX, text_scale, (255, 255, 255), text_thickness, cv2.LINE_AA)

                cv2.putText(stretched,
                    f"Focus: {focus_score:.1f}", (col3_x, image_height + 90),
                    cv2.FONT_HERSHEY_SIMPLEX, text_scale, (255, 255, 255), text_thickness, cv2.LINE_AA)


                cv2.line(stretched, (1, image_height + 108), (1079, image_height + 108), (255, 255, 255), 1, cv2.LINE_AA)

                cv2.putText(stretched,
                    f"Exposure: {get_camera_setting('exposure')}", (col1_x, image_height + 145),
                    cv2.FONT_HERSHEY_SIMPLEX, text_scale, (255, 255, 255), text_thickness, cv2.LINE_AA)

                cv2.putText(stretched,
                    f"Gain: {get_camera_setting('gain')}", (col2_x, image_height + 145),
                    cv2.FONT_HERSHEY_SIMPLEX, text_scale, (255, 255, 255), text_thickness, cv2.LINE_AA)

                cv2.putText(stretched,
                    f"Brightness: {brightness:.1f}", (col3_x, image_height + 145),
                    cv2.FONT_HERSHEY_SIMPLEX, text_scale, (255, 255, 255), text_thickness, cv2.LINE_AA)


                current_frame = stretched

                # Encode to JPEG and yield
                _, jpeg = cv2.imencode(".jpg", stretched, [cv2.IMWRITE_JPEG_QUALITY, 80])
                yield (b"--frame\r\n" b"Content-Type: image/jpeg\r\n\r\n" + jpeg.tobytes() + b"\r\n")

                # Frame rate control (~2 FPS for preview — matches grab thread interval)
                time.sleep(0.1)
            except GeneratorExit:
                raise  # Let GeneratorExit propagate — triggers finally cleanup
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, ConnectionError):
                logger.info("Stream: client disconnected (broken pipe)")
                break
            except Exception as e:
                logger.error(f"Stream generator error: {e}")
                break
    finally:
        with stream_consumers_lock:
            stream_consumers -= 1
            if stream_consumers <= 0:
                streaming_active = False
                stream_consumers = 0
                _grab_running = False
                if _grab_thread is not None and _grab_thread.is_alive():
                    _grab_thread.join(timeout=3.0)
                _grab_thread = None
                with _shared_camera_lock:
                    if _shared_camera is not None:
                        _shared_camera.close()
                        _shared_camera = None
                    _latest_frame = None
        logger.info(f"Stream consumer disconnected. Remaining consumers: {stream_consumers}")

def frame_generator_RPI() -> Generator[bytes, None, None]:
    """MJPEG stream generator for Raspberry Pi Camera Module 3."""
    global streaming_active, stream_consumers, _rpi_shared_camera
    global _latest_frame_rpi, _rpi_grab_thread, _rpi_grab_running
    
    #Frame modification parameters
    target_width = 1080
    text_scale = 1.2
    text_thickness = 2
    text_area_height = 160 # Schwarzer Informationsbereich: 1080 x 150 Pixel

    with stream_consumers_lock:
        stream_consumers += 1
        streaming_active = True

    logger.info(f"RPI stream consumer connected. Total: {stream_consumers}")

    # Get or create shared handler + start grabbing thread
    with _rpi_shared_camera_lock:
        handler = _rpi_shared_camera
        if handler is None:
            handler = SharedRPICamera()
            _rpi_shared_camera = handler
            _latest_frame_rpi = None
            _rpi_grab_thread = threading.Thread(
                target=_rpi_grabbing_loop, args=(handler,), daemon=True
            )
            _rpi_grab_thread.start()
            logger.info("Started RPI camera grabbing background thread")

    # Wait for camera to be ready (up to 30s)
    logger.info("Waiting for RPI camera to become available...")
    for _ in range(30):
        if handler.is_open:
            break
        time.sleep(1.0)
    logger.info(f"RPI camera availability check after 30s: is_open={handler.is_open}")

    if not handler.is_open:
        connecting = create_status_frame("Camera not available")
        _, jpeg = cv2.imencode(".jpg", connecting, [cv2.IMWRITE_JPEG_QUALITY, 80])
        yield (b"--frame\r\n" b"Content-Type: image/jpeg\r\n\r\n" + jpeg.tobytes() + b"\r\n")
        return

    try:
        local_frame_count = 0
        prev_zoom = None
        waiting_count = 0
        while True:
            try:
                is_capturing = get_camera_state("is_capturing") or False
                free_for_web = get_camera_state("free_for_web") or False
                if is_capturing or not free_for_web:
                    logger.info("RPI Stream: camera busy — exiting generator")
                    return

                zoom = get_camera_setting("zoom") or 2
                downscale = get_camera_setting("downscale") or 8
                if zoom != prev_zoom:
                    logger.info(f"RPI Stream: zoom={zoom}, downscale={downscale}")
                    prev_zoom = zoom

                # Read latest frame
                frame = None
                with _rpi_frame_lock:
                    if _latest_frame_rpi is not None:
                        frame = _latest_frame_rpi.copy()

                if frame is None or frame.ndim < 2 or frame.shape[0] < 10 or frame.shape[1] < 10:
                    time.sleep(0.25)
                    waiting_count += 1
                    connecting = create_status_frame("Waiting for camera")
                    _, jpeg = cv2.imencode(".jpg", connecting, [cv2.IMWRITE_JPEG_QUALITY, 80])
                    yield (b"--frame\r\n" b"Content-Type: image/jpeg\r\n\r\n" + jpeg.tobytes() + b"\r\n")
                    continue

                waiting_count = 0
                local_frame_count += 1

                # Calculate and overlay metrics (use pre-downscale frame for accuracy)
                focus_score = calculate_focus_score(frame)
                brightness = calculate_brightness(frame)

                # 1) Center-crop zoom first (before downscale, for accuracy)
                if zoom > 1:
                    h, w = frame.shape[:2]
                    crop_h = max(1, int(h // zoom))
                    crop_w = max(1, int(w // zoom))
                    y_start = max(0, int((h - crop_h) // 2))
                    x_start = max(0, int((w - crop_w) // 2))
                    frame = frame[y_start:y_start + crop_h, x_start:x_start + crop_w]

                # 2) Downscale to reduce processing time and bandwidth
                h, w = frame.shape[:2]
                if downscale > 1:
                    new_w = max(1, int(w // downscale))
                    new_h = max(1, int(h // downscale))
                    frame = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)

                # Apply min/max stretch for better visibility
                stretched = apply_min_max_stretch(frame)


                # Resize for streaming with target width of 1080 px width
                h, w = stretched.shape[:2]
                if w != target_width:
                    scale = target_width / w
                    new_height = max(1, int(h * scale))

                    interpolation = (cv2.INTER_AREA
                        if w > target_width
                        else cv2.INTER_LINEAR)

                    stretched = cv2.resize(stretched, (target_width, new_height), interpolation=interpolation)


                image_height = stretched.shape[0] # Höhe des eigentlichen Bildes merken


                # Add information area below the image
                text_area = np.zeros(
                (text_area_height, target_width, 3), dtype=stretched.dtype)
                stretched = np.vstack((stretched, text_area))


                # Spaltenpositionen
                col1_x = 1
                col2_x = 351
                col3_x = 701

                cv2.putText(stretched,
                    f"Height: {h}",(col1_x, image_height + 32),
                    cv2.FONT_HERSHEY_SIMPLEX, text_scale, (255, 255, 255), text_thickness, cv2.LINE_AA)

                cv2.putText(stretched,
                    f"Width: {w}", (col2_x, image_height + 32),
                    cv2.FONT_HERSHEY_SIMPLEX, text_scale, (255, 255, 255), text_thickness, cv2.LINE_AA)

                cv2.putText(stretched,
                    f"Frame: {local_frame_count}", (col3_x, image_height + 32),
                    cv2.FONT_HERSHEY_SIMPLEX, text_scale, (255, 255, 255), text_thickness, cv2.LINE_AA)


                cv2.line(stretched, (1, image_height + 53), (1079, image_height + 53), (255, 255, 255), 1, cv2.LINE_AA)

                cv2.putText(stretched,
                    f"Zoom: {zoom:.1f}", (col1_x, image_height + 90),
                    cv2.FONT_HERSHEY_SIMPLEX, text_scale, (255, 255, 255), text_thickness, cv2.LINE_AA)

                cv2.putText(stretched,
                    f"Downscale: {downscale:.1f}", (col2_x, image_height + 90),
                    cv2.FONT_HERSHEY_SIMPLEX, text_scale, (255, 255, 255), text_thickness, cv2.LINE_AA)

                cv2.putText(stretched,
                    f"Focus: {focus_score:.1f} @ {get_camera_setting('focus_diopter'):.1f}D", (col3_x, image_height + 90),
                    cv2.FONT_HERSHEY_SIMPLEX, text_scale, (255, 255, 255), text_thickness, cv2.LINE_AA)


                cv2.line(stretched, (1, image_height + 108), (1079, image_height + 108), (255, 255, 255), 1, cv2.LINE_AA)

                cv2.putText(stretched,
                    f"Exposure: {get_camera_setting('exposure')}", (col1_x, image_height + 145),
                    cv2.FONT_HERSHEY_SIMPLEX, text_scale, (255, 255, 255), text_thickness, cv2.LINE_AA)

                cv2.putText(stretched,
                    f"Gain: {get_camera_setting('gain')}", (col2_x, image_height + 145),
                    cv2.FONT_HERSHEY_SIMPLEX, text_scale, (255, 255, 255), text_thickness, cv2.LINE_AA)

                cv2.putText(stretched,
                    f"Brightness: {brightness:.1f}", (col3_x, image_height + 145),
                    cv2.FONT_HERSHEY_SIMPLEX, text_scale, (255, 255, 255), text_thickness, cv2.LINE_AA)


                _, jpeg = cv2.imencode(".jpg", stretched, [cv2.IMWRITE_JPEG_QUALITY, 80])
                yield (b"--frame\r\n" b"Content-Type: image/jpeg\r\n\r\n" + jpeg.tobytes() + b"\r\n")
                time.sleep(0.1)

            except GeneratorExit:
                raise
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                logger.info("RPI Stream: client disconnected")
                break
            except Exception as e:
                logger.error(f"RPI Stream generator error: {e}")
                break
    finally:
        with stream_consumers_lock:
            stream_consumers -= 1
            if stream_consumers <= 0:
                streaming_active = False
                stream_consumers = 0
                _rpi_grab_running = False
                if _rpi_grab_thread and _rpi_grab_thread.is_alive():
                    _rpi_grab_thread.join(timeout=3.0)
                _rpi_grab_thread = None
                with _rpi_shared_camera_lock:
                    if _rpi_shared_camera:
                        _rpi_shared_camera.close()
                        _rpi_shared_camera = None
                    _latest_frame_rpi = None
        logger.info(f"RPI stream consumer disconnected. Remaining: {stream_consumers}")


def create_status_frame(message: str) -> np.ndarray:
    """Create a status frame with a message."""
    # Load the waiting image from templates
    base_dir = os.path.dirname(os.path.abspath(__file__))
    img_path = os.path.join(base_dir, "templates", "Waiting_for_Camera.png")
    status_img = cv2.imread(img_path)
    logger.info(f"Creating status frame with message: {message}")
    
    if status_img is None:
        # Fallback if image not found
        status_img = np.zeros((480, 640, 3), dtype=np.uint8)
        status_img[:, :] = (40, 40, 40)
        cv2.putText(status_img, "LEPMON", (220, 200),
                    cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 255, 0), 3)
        cv2.putText(status_img, message, (50, 280),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        return status_img

    h, w = status_img.shape[:2]
    
    # Create text area below the image
    text_area_height = 120
    text_area = np.zeros((text_area_height, w, 3), dtype=status_img.dtype)
    text_area[:, :] = (20, 20, 35)  # Dark blue background matching UI theme
    
    # Add message and timestamp
    cv2.putText(text_area, message, (30, 50),
                cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)
    
    # Combine image and text area
    frame = np.vstack((status_img, text_area))
    
    return frame

########################################################################################################################
######### FastAPI Application
########################################################################################################################

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("Lepmon Web Service starting...")
    _start_viewer_cleanup()
    # Reset persistent viewer count — _CLIENT_REGISTRY is empty, old tokens are invalid.
    set_viewer_count(0)
    set_stream_viewers(0)
    yield
    _stop_viewer_cleanup()
    # Clean up on shutdown so no stale count persists across restarts.
    set_viewer_count(0)
    set_stream_viewers(0)
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
    try:
        sn = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "general", "serielnumber")
        title = f"ARNI {sn} Remote"
    except Exception:
        title = "ARNI Remote"
    try:
        firmware_version = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "software", "version")
    except Exception:
        firmware_version = "unknown"
    return templates.TemplateResponse(request, "index.html", {
        "title": title,
        "hardware_version": HARDWARE_VERSION,
        "firmware_version": firmware_version
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
        free_for_web = get_camera_state("free_for_web")
        web_requested = get_camera_state("web_requested")
        is_capturing = get_camera_state("is_capturing")
    except Exception:
        free_for_web = False
        web_requested = False
        is_capturing = False

    if not (free_for_web and web_requested):
        logger.info("Stream blocked: camera not free or not requested for web")
        placeholder = "/Capture_Image.png" if is_capturing else "/LEPMON_Logo_Circle.png"
        return RedirectResponse(url=placeholder)

    if EXPECTED_CAMERA_TYPE == "AV":
        return StreamingResponse(
            frame_generator_AV(),
            media_type="multipart/x-mixed-replace; boundary=frame"
        )

    elif EXPECTED_CAMERA_TYPE == "RPI":
        return StreamingResponse(
            frame_generator_RPI(),
            media_type="multipart/x-mixed-replace; boundary=frame"
        )

LEPMON_CONFIG_PATH = "/home/Ento/LepmonOS/Lepmon_config.json"


@app.get("/api/camera/power")
async def get_camera_power():
    """Return Camera_state.has_power from the in-memory cache."""
    try:
        has_power = get_camera_state("has_power")
    except Exception:
        has_power = False
    return {"has_power": bool(has_power)}


@app.get("/api/camera/state")
async def get_camera_state_api():
    """Return all Camera_state control parameters from the in-memory cache."""
    try:
        return {
            "has_power": bool(get_camera_state("has_power")),
            "is_detected": bool(get_camera_state("is_detected")),
            "is_capturing": bool(get_camera_state("is_capturing")),
            "free_for_web": bool(get_camera_state("free_for_web")),
            "web_requested": bool(get_camera_state("web_requested")),
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
    """Capture and return a single JPEG snapshot.

    Pre-conditions (all must be true):
      - Camera has power
      - Capturing is NOT active
      - Camera is free for web

    If any pre-condition fails, a 503 JSON error is returned.
    """
    # ---- Guard: check camera state ------------------------------------------------
    try:
        camera_has_power      = get_camera_state("has_power")
        camera_is_capturing   = get_camera_state("is_capturing")
        camera_free_for_web   = get_camera_state("free_for_web")
    except Exception:
        camera_has_power      = False
        camera_is_capturing   = False
        camera_free_for_web   = False

    # Also check capturing_state (cross-process)
    state = get_capturing_state()

    if not camera_has_power:
        return JSONResponse({"error 18": "Camera has no power"}, status_code=503)
    if camera_is_capturing or state.is_capturing:
        return JSONResponse(
            {"error 19": "Cannot capture snapshot while capturing is active"},
            status_code=503,
        )
    if not camera_free_for_web:
        return JSONResponse(
            {"error 20": "Camera is not free for web"},
            status_code=503,
        )

    # ---- Capture frame ------------------------------------------------------------
    frame = None
    if EXPECTED_CAMERA_TYPE == "RPI":
        # For RPI cameras, prefer the shared latest frame (if stream is running),
        # otherwise open a short-lived Picamera2 session to grab a single frame.
        with _rpi_frame_lock:
            if _latest_frame_rpi is not None:
                frame = _latest_frame_rpi.copy()
        if frame is None:
            frame = _capture_rpi_snapshot()
    else:
        # For AV cameras, always capture a dedicated full-resolution frame.
        # The streaming grab thread uses 2x2 binning (1/4 resolution), so we
        # must NOT read from the shared _latest_frame. Instead we open a
        # short-lived camera session with binning disabled (1x1).
        frame = _capture_av_snapshot()

    if frame is None:
        return JSONResponse({"error": "Failed to capture frame"}, status_code=500)

    # Apply min/max stretch (AV cameras only)
    if EXPECTED_CAMERA_TYPE == "AV":
        stretched = apply_min_max_stretch(frame)
    else:
        stretched = frame

    # Encode to JPEG
    _, jpeg = cv2.imencode('.jpg', stretched, [cv2.IMWRITE_JPEG_QUALITY, 95])

    return Response(
        content=jpeg.tobytes(),
        media_type="image/jpeg",
        headers={"Content-Disposition": "inline; filename=lepmon_snapshot.jpg"},
    )


@app.get("/api/status")
async def get_status():
    """Get current system status."""
    state = get_capturing_state()

    # Camera state from in-memory cache (fast, no I/O)
    try:
        camera_has_power = get_camera_state("has_power")
        camera_is_detected = get_camera_state("is_detected")
        camera_is_capturing = get_camera_state("is_capturing")
        camera_free_for_web = get_camera_state("free_for_web")
        camera_web_requested = get_camera_state("web_requested")
    except Exception:
        camera_has_power = False
        camera_is_detected = False
        camera_is_capturing = False
        camera_free_for_web = False
        camera_web_requested = False

    # Sync: if the grab thread detected the camera, report it as detected.
    # _last_camera_detected is set by the grabbing thread; the cache may lag.
    if _last_camera_detected:
        camera_is_detected = True

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
        "stream_viewers": len(_CLIENT_REGISTRY),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }


# ─── Viewer Registration API ──────────────────────────────────────────────────
# Every browser tab that loads the web UI registers here. On page unload it
# unregisters. This counts ALL active viewers regardless of stream state.


@app.post("/api/viewer/register")
async def register_viewer():
    """Register a new viewer. Called when the web page is loaded."""
    token = str(uuid.uuid4())
    with _CLIENT_REGISTRY_LOCK:
        _CLIENT_REGISTRY[token] = time.time()
        count = len(_CLIENT_REGISTRY)
    set_stream_viewers(count)  # in-memory cache + JSON persistence
    set_viewer_count(count)    # reliable /tmp file for cross-process reading
    logger.info(f"Viewer registered. Total viewers: {count} [{token[:8]}...]")
    return {"token": token}


@app.post("/api/viewer/unregister")
async def unregister_viewer(request: Request):
    """Unregister a viewer. Called when the web page is closed/reloaded."""
    token = ""
    # Try query parameter first (works with sendBeacon + query string)
    token = request.query_params.get("token", "")
    if not token:
        # Try JSON body
        try:
            body = await request.json()
            token = body.get("token", "")
        except Exception:
            pass
    if not token:
        return {"ok": False, "reason": "no token"}

    with _CLIENT_REGISTRY_LOCK:
        removed = token in _CLIENT_REGISTRY
        _CLIENT_REGISTRY.pop(token, None)
        count = len(_CLIENT_REGISTRY)
    set_stream_viewers(count)  # in-memory cache + JSON persistence
    set_viewer_count(count)    # reliable /tmp file for cross-process reading
    logger.info(f"Viewer {'unregistered' if removed else 'not found'}. Remaining viewers: {count}")
    return {"ok": True}


@app.post("/api/viewer/heartbeat")
async def viewer_heartbeat(request: Request):
    """Heartbeat: keeps the viewer alive. Called every 5 seconds by each active tab."""
    token = request.query_params.get("token", "")
    if not token:
        try:
            body = await request.json()
            token = body.get("token", "")
        except Exception:
            pass
    if not token:
        return {"ok": False, "reason": "no token"}

    with _CLIENT_REGISTRY_LOCK:
        if token in _CLIENT_REGISTRY:
            _CLIENT_REGISTRY[token] = time.time()
            return {"ok": True}
    return {"ok": False, "reason": "token not found"}


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
    """Get camera information.

    Prefers cached info from an active streaming session.
    Falls back to probing the VmbSystem directly when the stream is idle.

    CRITICAL: Do NOT probe when streaming is active — the SharedCamera
    already holds the camera. Opening it again causes "already in use"
    errors that corrupt the SDK state.
    """
    global _last_camera_model, _last_camera_serial, _last_camera_detected

    # Path 1: use cached info from the streaming session
    if _last_camera_detected and _last_camera_model:
        return {
            "available": True,
            "model": _last_camera_model,
            "serial": _last_camera_serial or "--",
            "interface_id": "--",
            "is_detected": True,
            "camera_type": EXPECTED_CAMERA_TYPE
        }

    # Path 2: probe the camera directly (ONLY when stream is idle)
    try:
        # DON'T probe if streaming is active — SharedCamera owns the camera
        if streaming_active:
            return {
                "available": True,
                "model": _last_camera_model or "Unknown",
                "serial": _last_camera_serial or "--",
                "interface_id": "--",
                "is_detected": _last_camera_detected,
                "camera_type": EXPECTED_CAMERA_TYPE
            }

        if _vmb_system is None:
            return {"available": False, "error": "VmbSystem not initialized", "is_detected": False, "camera_type": EXPECTED_CAMERA_TYPE}

        cams = _vmb_system.get_all_cameras()
        if cams:
            with cams[0] as cam:
                try:
                    _last_camera_model = cam.get_model()
                    _last_camera_serial = cam.get_serial()
                    _last_camera_detected = True
                except Exception:
                    pass
                return {
                    "available": True,
                    "model": _last_camera_model or "Unknown",
                    "serial": _last_camera_serial or "--",
                    "interface_id": cam.get_interface_id(),
                    "is_detected": True,
                    "camera_type": EXPECTED_CAMERA_TYPE
                }
        else:
            return {"available": False, "error": "No camera found", "is_detected": False, "camera_type": EXPECTED_CAMERA_TYPE}
    except Exception as e:
        logger.warning(f"Camera info probe failed: {e}")
        return {"available": False, "error": str(e), "is_detected": False, "camera_type": EXPECTED_CAMERA_TYPE}


@app.get("/api/focus")
async def get_focus_score():
    """Get current focus score without capturing a new frame."""
    try:
        global current_frame

        if current_frame is not None:
            score = calculate_focus_score(current_frame)
            return {"focus_score": score, "is_sharp": score >= 225.0}
        else:
            return {"focus_score": 0.0, "is_sharp": False, "error": "No frame available"}
    except Exception as e:
        logger.error(f"Focus endpoint error: {e}")
        return {"focus_score": 0.0, "is_sharp": False, "error": str(e)}


@app.get("/api/camera/settings")
async def get_camera_settings():
    """Get current camera settings from in-memory cache."""
    result = {
        "exposure": get_camera_setting("exposure"),
        "gain": get_camera_setting("gain"),
        "stream_downscale": get_camera_setting("downscale"),
        "stream_zoom": get_camera_setting("zoom"),
        "focus_mode": get_camera_setting("focus_mode"),
        "lens_position": get_camera_setting("lens_position"),
        "focus_diopter_pos": get_camera_setting("focus_diopter_pos"),
        "focus_diopter": get_camera_setting("focus_diopter"),  # primary focus control (diopter)
    }
    return result


@app.post("/api/camera/settings")
async def update_camera_settings(settings: dict):
    """Update camera settings in the in-memory cache.

    Settings are stored in RAM so they take effect immediately for the
    live stream — no file I/O or permission issues.

    Supported keys:
      - exposure         (float, 1–10000 ms)
      - gain             (float, 0–48 dB)
      - stream_downscale (int,   1–20)
      - stream_zoom      (int,   1–5)
      - focus_diopter    (float, -15–1)  CSS_Gen_1 only
    """
    try:
        exposure = settings.get("exposure")
        gain = settings.get("gain")
        stream_downscale = settings.get("stream_downscale")
        stream_zoom = settings.get("stream_zoom")
        focus_diopter = settings.get("focus_diopter")
        focus_diopter_pos = settings.get("focus_diopter_pos")  # manual lens position for non-CSS_Gen_1

        # Validate and sanitize
        if exposure is not None:
            exposure = max(1, min(10000, float(exposure)))
            set_camera_setting("exposure", exposure)
        if gain is not None:
            gain = max(0, min(48, float(gain)))
            set_camera_setting("gain", gain)
        if stream_downscale is not None:
            stream_downscale = max(1.0, min(5.0, float(stream_downscale)))
            set_camera_setting("downscale", stream_downscale)
        if stream_zoom is not None:
            stream_zoom = max(1, min(5, int(stream_zoom)))
            set_camera_setting("zoom", stream_zoom)
        if focus_diopter is not None:
            focus_diopter = max(-15, min(1, float(focus_diopter)))
            set_camera_setting("focus_diopter", focus_diopter)
        if focus_diopter_pos is not None:
            focus_diopter_pos = max(0.0, min(10.0, float(focus_diopter_pos)))
            set_camera_setting("focus_diopter_pos", focus_diopter_pos)

        # Log the new values
        logger.info(
            f"Camera settings updated in cache: "
            f"exposure={get_camera_setting('exposure')}, "
            f"gain={get_camera_setting('gain')}, "
            f"downscale={get_camera_setting('downscale')}, "
            f"zoom={get_camera_setting('zoom')}"
            + (f", focus_diopter={get_camera_setting('focus_diopter')}" if HARDWARE_VERSION == "CSS_Gen_1" else "")
        )

        # Attempt to persist to JSON file (best-effort, non-blocking)
        try:
            _persist_camera_settings_to_file()
        except Exception as e:
            logger.warning(
                f"Could not persist camera settings to Lepmon_config.json: {e}. "
                "Settings are active in memory but will be lost on restart."
            )

        return {"success": True, "message": "Settings applied"}
    except Exception as e:
        logger.error(f"Failed to update camera settings: {e}")
        return {"success": False, "error": str(e)}


# Exposure mode: 'auto' (default) or 'manual'
exposure_mode = "auto"


@app.get("/api/camera/exposure_mode")
async def get_exposure_mode():
    """Get current exposure mode."""
    return {"mode": exposure_mode}


@app.post("/api/camera/exposure_mode")
async def set_exposure_mode(mode_data: dict):
    """Set exposure mode (auto or manual)."""
    global exposure_mode
    mode = mode_data.get("mode", "auto")
    if mode not in ("auto", "manual"):
        mode = "auto"
    exposure_mode = mode
    # Also store in camera settings cache so grab_thread can read it
    set_camera_setting("_exposure_mode", mode)
    logger.info(f"Exposure mode set to: {exposure_mode}")
    return {"mode": exposure_mode}


# ── Focus mode: 'auto' (autofocus) or 'manual' (fixed lens position) ──

@app.get("/api/camera/focus_mode")
async def get_focus_mode():
    """Get current focus mode."""
    return {"mode": get_camera_setting("focus_mode") or "manual"}


@app.post("/api/camera/focus_mode")
async def set_focus_mode(mode_data: dict):
    """Set focus mode (auto or manual).

    In auto mode the camera runs continuous autofocus and the current
    LensPosition is reported back every 10 frames.
    In manual mode the user-supplied focus_diopter_pos (0.0–10.0) is
    applied as a fixed LensPosition.
    """
    mode = mode_data.get("mode", "manual")
    if mode not in ("auto", "manual"):
        mode = "manual"
    set_camera_setting("focus_mode", mode)
    logger.info(f"Focus mode set to: {mode}")
    return {"mode": mode}


def _persist_camera_settings_to_file() -> None:
    """Best-effort attempt to write current camera settings to Lepmon_config.json.

    This may fail due to permissions — that's OK, the in-memory cache is the
    source of truth. A restart will re-read the file, so persistent storage
    is still desired when possible.
    """
    config_path = "/home/Ento/LepmonOS/Lepmon_config.json"
    for section in ["Camera_Stream"]:
        for key, cache_key in [("exposure", "exposure"), ("gain", "gain"),
                               ("downscale", "downscale"), ("zoom", "zoom")]:
            val = get_camera_setting(cache_key)
            if val is not None:
                write_value_to_section(config_path, section, key, val)
    logger.info(f"Camera settings persisted to {config_path}")

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


# ── USB Download ──────────────────────────────────────────────────
# Cache of Lepmon files for streaming download
_usb_download_files = []
_usb_download_count = 0


def _refresh_usb_download_files() -> list:
    """Collect all files inside Lepmon#SN* directories on USB."""
    global _usb_download_files, _usb_download_count
    files = []
    usb_path = find_usb_mount()
    if usb_path:
        for entry in os.listdir(usb_path):
            if entry.startswith("Lepmon#SN"):
                dirpath = os.path.join(usb_path, entry)
                if os.path.isdir(dirpath):
                    for root, dirs, filenames in os.walk(dirpath):
                        for fname in filenames:
                            files.append(os.path.join(root, fname))
    _usb_download_files = files
    _usb_download_count = len(files)
    return files


@app.get("/api/usb/count")
async def get_usb_file_count():
    """Count files in Lepmon#SN* directories on USB."""
    _refresh_usb_download_files()
    usb_path = find_usb_mount()
    return {
        "mounted": usb_path is not None,
        "count": _usb_download_count,
        "path": usb_path
    }


@app.get("/api/usb/files")
async def get_usb_files():
    """Get list of all Lepmon#SN* files with relative paths."""
    global _usb_download_files
    if not _usb_download_files:
        _refresh_usb_download_files()
    
    usb_path = find_usb_mount()
    files = []
    for filepath in _usb_download_files:
        if os.path.isfile(filepath):
            rel = os.path.relpath(filepath, usb_path) if usb_path else os.path.basename(filepath)
            files.append({
                "path": filepath,
                "rel": rel,
                "name": os.path.basename(filepath),
                "size": os.path.getsize(filepath),
            })
    return {"files": files}


@app.get("/api/usb/raw/{rel:path}")
async def download_usb_file(rel: str):
    """Download a single file from USB by relative path (no Content-Disposition)."""
    global _usb_download_files
    if not _usb_download_files:
        _refresh_usb_download_files()
    
    usb_path = find_usb_mount()
    if not usb_path:
        return JSONResponse({"error": "USB not mounted"}, status_code=404)
    
    # Sanitize path to prevent directory traversal
    safe_rel = os.path.normpath(rel).lstrip("./\\")
    full = os.path.join(usb_path, safe_rel)
    
    if not os.path.isfile(full):
        return JSONResponse({"error": "File not found"}, status_code=404)
    
    try:
        with open(full, "rb") as f:
            content = f.read()
    except OSError as e:
        logger.warning(f"Failed to read {full}: {e}")
        return JSONResponse({"error": "File read error"}, status_code=503)
    
    ext = os.path.splitext(full)[1].lower()
    mime_map = {
        '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
        '.png': 'image/png', '.tif': 'image/tiff',
        '.tiff': 'image/tiff', '.bmp': 'image/bmp',
        '.csv': 'text/csv', '.log': 'text/plain',
    }
    mime = mime_map.get(ext, 'application/octet-stream')
    
    return Response(content=content, media_type=mime)


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


# --- HTTPS Configuration ---
_SSL_DIR = os.path.expanduser("~/.lepmon_ssl")
_SSL_CERT = os.path.join(_SSL_DIR, "lepmon.crt")
_SSL_KEY = os.path.join(_SSL_DIR, "lepmon.key")

def _ensure_https_cert():
    """Generate a self-signed certificate if it doesn't exist."""
    if os.path.exists(_SSL_CERT) and os.path.exists(_SSL_KEY):
        return True
    
    os.makedirs(_SSL_DIR, exist_ok=True)
    try:
        subprocess.run([
            "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
            "-keyout", _SSL_KEY, "-out", _SSL_CERT, "-days", "3650",
            "-subj", "/CN=LepmonOS",
        ], check=True, capture_output=True)
        logger.info(f"Created self-signed SSL certificate at {_SSL_CERT}")
        return True
    except Exception as e:
        logger.error(f"Failed to create SSL certificate: {e}")
        return False

def run_server(host: str = "0.0.0.0", port: int = 8080):
    """Run the FastAPI server with HTTPS support."""
    has_ssl = _ensure_https_cert()
    
    config = {
        "app": app,
        "host": host,
        "port": port,
        "log_level": "info",
    }
    
    if has_ssl:
        config["ssl_certfile"] = _SSL_CERT
        config["ssl_keyfile"] = _SSL_KEY
        logger.info(f"Starting Lepmon Web Service on https://{host}:{port}")
    else:
        logger.warning(f"Starting Lepmon Web Service on http://{host}:{port} (no SSL)")

    uvicorn.run(**config)


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
    # Start camera state JSON-sync (2s interval — keeps cache in sync with other processes)
    _start_camera_state_sync()
    # Start camera release monitor (5s interval — frees camera when free_for_web is False)
    _start_camera_release_monitor()
    # Start viewer heartbeat cleanup (now handled by lifespan, no longer started here)
    run_server(args.host, args.port)

