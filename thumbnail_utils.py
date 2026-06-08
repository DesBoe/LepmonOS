#!/usr/bin/env python3
"""
Thumbnail helpers shared between the capture loop and the web service.

Raw images on the USB drive may be 16-bit TIFFs (Allied Vision Mono12/Bayer
or RPi HQ DNG). Reading them with the default cv2.imread silently truncates
to 8-bit by dropping the high byte, producing near-black previews.

Generate 320 px JPEGs at capture time and stash them in a .thumbs/ shadow
tree that mirrors the original directory structure, so the gallery endpoint
serves precomputed bytes without re-decoding the raw on every request.
"""

import logging
import os
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)

THUMBS_DIR_NAME = ".thumbs"
THUMB_MAX_PX = 320


def find_usb_mount() -> Optional[str]:
    """First mounted USB partition under /media/Ento, or None."""
    media_path = "/media/Ento"
    if not os.path.exists(media_path):
        return None
    for item in os.listdir(media_path):
        full = os.path.join(media_path, item)
        if os.path.ismount(full):
            return full
    return None


def thumb_path_for(image_path: str) -> Optional[str]:
    """
    /media/Ento/<usb>/2024/img.tif → /media/Ento/<usb>/.thumbs/2024/img.tif.jpg
    Returns None if image_path is not under any mounted USB drive.
    """
    usb_path = find_usb_mount()
    if not usb_path:
        return None
    try:
        rel = os.path.relpath(image_path, usb_path)
    except ValueError:
        return None
    if rel.startswith(".."):
        return None
    return os.path.join(usb_path, THUMBS_DIR_NAME, rel + ".jpg")


def stretch_to_8bit(frame: np.ndarray) -> np.ndarray:
    """Normalize an arbitrary-depth image to uint8 via min/max stretch."""
    if frame.dtype == np.uint8:
        return frame
    out = np.empty(frame.shape, dtype=np.uint8)
    cv2.normalize(frame, out, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)
    return out


def make_thumbnail_bytes(image_path: str, max_size: int = THUMB_MAX_PX) -> Optional[bytes]:
    """
    Read (16-bit safe), stretch to 8-bit, resize, JPEG-encode.
    Returns bytes or None on failure.
    """
    frame = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
    if frame is None:
        return None

    frame = stretch_to_8bit(frame)
    if frame.ndim == 2:
        frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)

    h, w = frame.shape[:2]
    scale = min(max_size / w, max_size / h, 1.0)
    if scale < 1.0:
        frame = cv2.resize(frame, (int(w * scale), int(h * scale)),
                           interpolation=cv2.INTER_AREA)

    ok, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
    if not ok:
        return None
    return jpeg.tobytes()


def write_thumbnail_for(image_path: str, max_size: int = THUMB_MAX_PX) -> Optional[str]:
    """
    Generate and persist a thumbnail in the .thumbs/ shadow tree.
    Returns the thumbnail path on success, None on any failure (logged).
    Safe to call from the capture loop — never raises.
    """
    try:
        thumb_path = thumb_path_for(image_path)
        if thumb_path is None:
            return None

        os.makedirs(os.path.dirname(thumb_path), exist_ok=True)

        data = make_thumbnail_bytes(image_path, max_size)
        if data is None:
            logger.warning("Could not decode %s for thumbnail", image_path)
            return None

        with open(thumb_path, 'wb') as f:
            f.write(data)
        return thumb_path
    except Exception as e:
        logger.warning("write_thumbnail_for(%s) failed: %s", image_path, e)
        return None
