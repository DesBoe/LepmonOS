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
import uvicorn
import os
import sys
import json
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Optional, Generator
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import capturing state module
from capturing_state import get_capturing_state, CaptureState

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


def get_vimba_frame(exposure: int = DEFAULT_EXPOSURE, gain: float = DEFAULT_GAIN) -> Optional[np.ndarray]:
    """
    Capture a single frame from the Allied Vision camera using VmbPy SDK.
    Returns the frame as a numpy array or None if capture fails.
    """
    try:
        from vmbpy import VmbSystem, PixelFormat, PersistType
        
        with VmbSystem.get_instance() as vmb:
            cams = vmb.get_all_cameras()
            if not cams:
                logger.warning("No Allied Vision camera found")
                return None
            
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
    except Exception as e:
        logger.error(f"Error capturing frame: {e}")
        return None


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
            # Check if capturing is active - if so, don't compete for camera
            state = get_capturing_state()
            if state.is_capturing:
                # Send a status frame instead
                status_frame = create_status_frame("Capturing in progress...")
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
    lifespan=lifespan
)

# Setup templates
templates_dir = Path(__file__).parent / "templates"
templates_dir.mkdir(exist_ok=True)
templates = Jinja2Templates(directory=str(templates_dir))


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
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }


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
