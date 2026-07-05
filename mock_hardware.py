"""Mock hardware objects used by dev_mode.DEV_MODE code paths.

These stand in for the DS3231 RTC, the INA226 power sensor, the
BH1750/PCT2075/BME280 environmental sensors, and the camera frame source so
the software can run end-to-end (start_up -> capturing -> web streaming)
without any of that hardware attached.
"""
import random
import time

import cv2
import numpy as np


class MockRTC:
    """Stands in for adafruit_ds3231.DS3231. Backed by the system clock."""

    def __init__(self):
        self.alarm1 = None
        self.alarm2 = None
        self.alarm1_status = False
        self.alarm2_status = False
        self.alarm1_interrupt = False
        self.alarm2_interrupt = False
        self.lost_power = False

    @property
    def datetime(self):
        return time.localtime()

    @datetime.setter
    def datetime(self, value):
        # System time is the source of truth in DEV mode; nothing to persist.
        pass


class MockINA226:
    """Stands in for ina226.INA226. Returns plausible, jittered readings."""

    def voltage(self):
        return round(12.0 + random.uniform(-0.2, 0.2), 3)

    def shunt_voltage(self):
        return round(random.uniform(5, 40), 3)

    def current(self):
        return round(random.uniform(100, 400), 3)

    def power(self):
        return round(random.uniform(1200, 3600), 3)  # mW


def mock_lux():
    return round(random.uniform(50, 500), 2)


def mock_inner_temp():
    return round(random.uniform(18, 28), 2)


def mock_outer_climate():
    """Returns (temperature_C, pressure_hPa, humidity_pct)."""
    return (
        round(random.uniform(10, 25), 2),
        round(random.uniform(980, 1030), 2),
        round(random.uniform(30, 70), 2),
    )


def generate_mock_frame(width=640, height=480, label="DEV MODE"):
    """Synthetic gradient test frame, stamped with a label and timestamp."""
    width = int(width) if width else 640
    height = int(height) if height else 480

    frame = np.zeros((height, width, 3), dtype=np.uint8)
    rows = np.linspace(0, 255, height, dtype=np.uint8).reshape(height, 1)
    frame[:, :, 0] = rows
    frame[:, :, 2] = 255 - rows

    scale = max(width / 640, 1.0)
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    cv2.putText(frame, f"{label} - {timestamp}", (10, int(30 * scale)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8 * scale, (255, 255, 255), max(int(2 * scale), 1))
    cv2.putText(frame, f"{width}x{height} mock frame", (10, int(70 * scale)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8 * scale, (0, 255, 255), max(int(2 * scale), 1))
    return frame
