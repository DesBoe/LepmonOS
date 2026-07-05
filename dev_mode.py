"""Global emulation-mode flag for running LepmonOS without attached hardware.

Enable with:  export LEPMON_DEV_MODE=1
When unset (or not "1"), every module behaves exactly as it does today.
"""
import os

DEV_MODE = os.environ.get("LEPMON_DEV_MODE", "").strip() == "1"
DEV_MODE = True
_warned = set()


def note_mock(name):
    """Print a one-time notice that a mocked hardware component is in use."""
    if name not in _warned:
        print(f"[DEV MODE] using mocked {name}")
        _warned.add(name)
