#!/usr/bin/env python3
"""
Capturing State Module - Shared state management for Lepmon system.

This module provides a thread-safe mechanism to track the capturing state
between the main Lepmon application and the web service.

The state is stored in a shared file to allow communication between
potentially separate processes.
"""

import threading
import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional


# State file location - use a tmpfs location for fast access
STATE_FILE = "/tmp/lepmon_capture_state.json"
STATE_LOCK = threading.Lock()


@dataclass
class CaptureState:
    """Represents the current capturing state."""
    is_capturing: bool = False
    start_time: Optional[datetime] = None
    images_captured: int = 0
    current_exposure: int = 140
    current_gain: float = 5.0
    last_image_path: Optional[str] = None
    error_message: Optional[str] = None
    stop_requested: bool = False
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "is_capturing": self.is_capturing,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "images_captured": self.images_captured,
            "current_exposure": self.current_exposure,
            "current_gain": self.current_gain,
            "last_image_path": self.last_image_path,
            "error_message": self.error_message,
            "stop_requested": self.stop_requested
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'CaptureState':
        """Create instance from dictionary."""
        start_time = None
        if data.get("start_time"):
            try:
                start_time = datetime.fromisoformat(data["start_time"])
            except (ValueError, TypeError):
                pass
        
        return cls(
            is_capturing=data.get("is_capturing", False),
            start_time=start_time,
            images_captured=data.get("images_captured", 0),
            current_exposure=data.get("current_exposure", 140),
            current_gain=data.get("current_gain", 5.0),
            last_image_path=data.get("last_image_path"),
            error_message=data.get("error_message"),
            stop_requested=data.get("stop_requested", False)
        )


def _write_state(state: CaptureState) -> None:
    """Write state to file (internal use)."""
    try:
        with open(STATE_FILE, 'w') as f:
            json.dump(state.to_dict(), f)
    except Exception as e:
        print(f"Warning: Could not write capture state: {e}")


def _read_state() -> CaptureState:
    """Read state from file (internal use)."""
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, 'r') as f:
                data = json.load(f)
                return CaptureState.from_dict(data)
    except Exception as e:
        print(f"Warning: Could not read capture state: {e}")
    
    return CaptureState()


def get_capturing_state() -> CaptureState:
    """
    Get the current capturing state.
    Thread-safe read operation.
    
    Returns:
        CaptureState: Current state of the capturing system.
    """
    with STATE_LOCK:
        return _read_state()


def set_capturing_active(active: bool = True) -> None:
    """
    Set the capturing state to active or inactive.
    
    Args:
        active: True when capturing loop starts, False when it ends.
    """
    with STATE_LOCK:
        state = _read_state()
        state.is_capturing = active
        if active:
            state.start_time = datetime.now()
            state.images_captured = 0
            state.stop_requested = False
            state.error_message = None
        else:
            state.start_time = None
        _write_state(state)


def update_capture_progress(
    images_captured: Optional[int] = None,
    current_exposure: Optional[int] = None,
    current_gain: Optional[float] = None,
    last_image_path: Optional[str] = None,
    error_message: Optional[str] = None
) -> None:
    """
    Update the capturing progress information.
    
    Args:
        images_captured: Total images captured in this session.
        current_exposure: Current exposure setting in ms.
        current_gain: Current gain setting.
        last_image_path: Path to the last captured image.
        error_message: Any error message to report.
    """
    with STATE_LOCK:
        state = _read_state()
        
        if images_captured is not None:
            state.images_captured = images_captured
        if current_exposure is not None:
            state.current_exposure = current_exposure
        if current_gain is not None:
            state.current_gain = current_gain
        if last_image_path is not None:
            state.last_image_path = last_image_path
        if error_message is not None:
            state.error_message = error_message
        
        _write_state(state)


def increment_image_count() -> int:
    """
    Increment the image counter by one.
    
    Returns:
        int: New image count.
    """
    with STATE_LOCK:
        state = _read_state()
        state.images_captured += 1
        _write_state(state)
        return state.images_captured


def request_stop_capture() -> None:
    """
    Request the capturing loop to stop.
    The main loop should periodically check this flag.
    """
    with STATE_LOCK:
        state = _read_state()
        state.stop_requested = True
        _write_state(state)


def is_stop_requested() -> bool:
    """
    Check if a stop has been requested.
    
    Returns:
        bool: True if stop was requested.
    """
    with STATE_LOCK:
        state = _read_state()
        return state.stop_requested


def clear_stop_request() -> None:
    """Clear the stop request flag."""
    with STATE_LOCK:
        state = _read_state()
        state.stop_requested = False
        _write_state(state)


def reset_state() -> None:
    """Reset the state to initial values."""
    with STATE_LOCK:
        _write_state(CaptureState())


# Initialize state file on module load
def _initialize_state():
    """Initialize state file if it doesn't exist."""
    if not os.path.exists(STATE_FILE):
        reset_state()


_initialize_state()


if __name__ == "__main__":
    # Test the module
    print("Testing capturing state module...")
    
    # Reset state
    reset_state()
    print(f"Initial state: {get_capturing_state()}")
    
    # Set capturing active
    set_capturing_active(True)
    state = get_capturing_state()
    print(f"After starting capture: is_capturing={state.is_capturing}")
    
    # Update progress
    update_capture_progress(images_captured=5, current_exposure=150)
    state = get_capturing_state()
    print(f"After update: images={state.images_captured}, exposure={state.current_exposure}")
    
    # Increment counter
    count = increment_image_count()
    print(f"After increment: images={count}")
    
    # Request stop
    request_stop_capture()
    print(f"Stop requested: {is_stop_requested()}")
    
    # Set inactive
    set_capturing_active(False)
    state = get_capturing_state()
    print(f"After stopping: is_capturing={state.is_capturing}")
    
    print("All tests passed!")
