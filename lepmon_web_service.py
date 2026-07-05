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
from fastapi import FastAPI, Response, Request
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
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

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import capturing state module
from capturing_state import (
    get_capturing_state,
    CaptureState,
    is_web_focus_active,
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

# Camera settings
CAMERA_SETTINGS_FILE = "/home/Ento/LepmonOS/camera_web_settings.json"
DEFAULT_EXPOSURE = 140  # ms
DEFAULT_GAIN = 5
STREAM_DOWNSCALE = 4  # Downscale factor for streaming (reduces bandwidth)

# Global camera settings (loaded from file)
camera_settings = {
    "exposure": DEFAULT_EXPOSURE,
    "gain": DEFAULT_GAIN
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
                settings_file = '/home/Ento/LepmonOS/Kamera_Einstellungen.xml'
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
    Otherwise we yield a low-rate status placeholder.
    """
    global current_frame, streaming_active, stream_consumers

    with stream_consumers_lock:
        stream_consumers += 1
        streaming_active = True

    logger.info(f"Stream consumer connected. Total consumers: {stream_consumers}")

    try:
        # Use global camera settings
        exposure = camera_settings["exposure"]
        gain = camera_settings["gain"]

        while True:
            state = get_capturing_state()

            # Timelapse wins — never compete with it.
            if state.is_capturing:
                status_frame = create_status_frame("Capturing in progress...")
                _, jpeg = cv2.imencode('.jpg', status_frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')
                time.sleep(1.0)
                continue

            # No web focus session — show a hint instead of grabbing the camera.
            if not state.web_focus_active:
                status_frame = create_status_frame("Open Web Focus on device menu")
                _, jpeg = cv2.imencode('.jpg', status_frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')
                time.sleep(1.0)
                continue
            
            # Capture frame from camera
            with camera_lock:
                frame = get_vimba_frame(exposure, gain)
            
            if frame is not None:
                # Downscale raw image first to reduce processing time
                h, w = frame.shape[:2]
                if STREAM_DOWNSCALE > 1:
                    new_w = w // STREAM_DOWNSCALE
                    new_h = h // STREAM_DOWNSCALE
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
                cv2.putText(stretched, f"Exp: {exposure}ms Gain: {gain}", (10, 90),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                cv2.putText(stretched, f"Scale: 1/{STREAM_DOWNSCALE}", (10, 120),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                
                current_frame = stretched
                
                # Encode to JPEG
                _, jpeg = cv2.imencode('.jpg', stretched, [cv2.IMWRITE_JPEG_QUALITY, 80])
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')
            else:
                # Generate error frame
                error_frame = create_status_frame("Camera not available")
                _, jpeg = cv2.imencode('.jpg', error_frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')
            
            # Frame rate control (~5 FPS for preview)
            time.sleep(0.2)
            
    except GeneratorExit:
        logger.info("Stream consumer disconnected")
    finally:
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
    return templates.TemplateResponse("index.html", {
        "request": request,
        "title": "Lepmon Camera Monitor"
    })


@app.get("/stream")
async def video_stream():
    """MJPEG video stream endpoint."""
    return StreamingResponse(
        frame_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


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

    return {
        "is_capturing": state.is_capturing,
        "capture_start_time": state.start_time.isoformat() if state.start_time else None,
        "images_captured": state.images_captured,
        "stream_active": streaming_active,
        "stream_consumers": stream_consumers,
        "web_focus_active": state.web_focus_active,
        "web_focus_started_at": state.web_focus_started_at.isoformat() if state.web_focus_started_at else None,
        "stop_focus_requested": state.stop_focus_requested,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }


@app.post("/api/focus/stop")
async def request_focus_stop():
    """
    Ask the OLED loop to end the active web focus session.

    The OLED polling loop sees the flag, clears web_focus_active,
    releases the camera, and returns to the main menu. Safe to call
    repeatedly or when no session is active.
    """
    state = get_capturing_state()
    if not state.web_focus_active:
        return {"message": "No active focus session", "web_focus_active": False}

    request_stop_focus()
    return {"message": "Stop request sent", "web_focus_active": True}


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
                        "interface_id": cam.get_interface_id()
                    }
            else:
                return {"available": False, "error": "No camera found"}
    except ImportError:
        return {"available": False, "error": "VmbPy SDK not installed"}
    except Exception as e:
        return {"available": False, "error": str(e)}


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
    """Update camera settings and save to file."""
    global camera_settings
    
    try:
        # Validate and update settings
        if "exposure" in settings:
            exposure = float(settings["exposure"])
            if 1 <= exposure <= 10000:  # 1ms to 10s
                camera_settings["exposure"] = exposure
            else:
                return JSONResponse(
                    {"error": "Exposure must be between 1 and 10000 ms"},
                    status_code=400
                )
        
        if "gain" in settings:
            gain = float(settings["gain"])
            if 0 <= gain <= 48:  # Typical range for Allied Vision cameras
                camera_settings["gain"] = gain
            else:
                return JSONResponse(
                    {"error": "Gain must be between 0 and 48"},
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
    Returns list of dicts with path, filename, modified time, and size.
    The .thumbs/ shadow tree is skipped so precomputed previews don't
    show up in the gallery as their own entries.
    """
    usb_path = find_usb_mount()
    if not usb_path:
        return []

    image_extensions = ('.jpg', '.jpeg', '.png', '.tif', '.tiff', '.bmp')
    images = []

    for root, dirs, files in os.walk(usb_path):
        dirs[:] = [d for d in dirs if d != THUMBS_DIR_NAME]
        for f in files:
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
        # Create a safe ID from the path for the serving endpoint
        rel_path = img["path"]
        from datetime import datetime
        mod_time = datetime.fromtimestamp(img["modified"])
        result.append({
            "filename": img["filename"],
            "url": f"/api/images/file?path={img['path']}",
            "thumbnail_url": f"/api/images/thumbnail?path={img['path']}",
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

    with open(path, 'rb') as f:
        data = f.read()

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
    if not os.path.isfile(path):
        return JSONResponse({"error": "File not found"}, status_code=404)

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
    
    run_server(args.host, args.port)
