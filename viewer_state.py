#!/usr/bin/env python3
"""
Viewer State Module - Tracks active web UI viewers across processes.

Used for inter-process communication between:
- lepmon_web_service.py (writes: registers/unregisters viewers)
- end.py, Main.py, etc. (reads: how many viewers are watching)

Stored in /tmp/ so that all processes regardless of user can read/write.
"""

import threading
import json
import os
import time

# State file location - /tmp is writable by all users and survives reboots.
VIEWER_STATE_FILE = "/tmp/lepmon_viewer_state.json"
VIEWER_STATE_LOCK = threading.Lock()


def _write_viewer_state(count: int) -> None:
    """Write viewer count to file (internal use)."""
    try:
        with open(VIEWER_STATE_FILE, 'w') as f:
            json.dump({"stream_viewers": count}, f)
    except Exception as e:
        print(f"Warning: Could not write viewer state: {e}")


def _read_viewer_state() -> int:
    """Read viewer count from file (internal use)."""
    try:
        if os.path.exists(VIEWER_STATE_FILE):
            with open(VIEWER_STATE_FILE, 'r') as f:
                data = json.load(f)
                return int(data.get("stream_viewers", 0))
    except Exception as e:
        print(f"Warning: Could not read viewer state: {e}")
    return 0


def set_viewer_count(count: int) -> None:
    """Set the number of active viewers (thread-safe, writes to /tmp file)."""
    with VIEWER_STATE_LOCK:
        _write_viewer_state(count)


def get_viewer_count() -> int:
    """Get the current number of active viewers (thread-safe, reads from /tmp file)."""
    with VIEWER_STATE_LOCK:
        return _read_viewer_state()


# Initialize file on module load (only if it doesn't already exist)
if not os.path.exists(VIEWER_STATE_FILE):
    _write_viewer_state(0)


if __name__ == "__main__":
    print("Testing viewer state module...")
    print(f"Initial: {get_viewer_count()} viewers")
    set_viewer_count(1)
    print(f"After set(1): {get_viewer_count()} viewers")
    set_viewer_count(3)
    print(f"After set(3): {get_viewer_count()} viewers")
    set_viewer_count(0)
    print(f"After set(0): {get_viewer_count()} viewers")
    print("All tests passed!, start monitoring:")

    while True:
        time_stamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        count = get_viewer_count()
        print(f"timestamp: {time_stamp}, Current viewers: {count}")
        time.sleep(2)

