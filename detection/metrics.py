"""Eye and mouth metrics computed from face landmarks.

These functions take a (N, 2) NumPy array of pixel coordinates, where N is the
number of MediaPipe Face Mesh landmarks (468, or 478 with refined landmarks).
They do not touch the camera, so they can be unit-tested with synthetic points.
"""
from __future__ import annotations

import numpy as np

# MediaPipe Face Mesh indices, ordered p1..p6 for the EAR formula.
# p1 and p4 are the horizontal corners; p2/p3 are upper lid; p5/p6 are lower lid.
LEFT_EYE = [362, 385, 387, 263, 373, 380]
RIGHT_EYE = [33, 160, 158, 133, 153, 144]

# Mouth: left corner, right corner, upper lip, lower lip.
MOUTH = [78, 308, 13, 14]


def eye_aspect_ratio(pts: np.ndarray) -> float:
    """Eye Aspect Ratio (Soukupová & Čech, 2016) for six eye points p1..p6.

    EAR = (|p2 - p6| + |p3 - p5|) / (2 * |p1 - p4|)
    The value is about 0.3 for an open eye and drops toward 0 as the eye closes.
    """
    vertical_1 = np.linalg.norm(pts[1] - pts[5])
    vertical_2 = np.linalg.norm(pts[2] - pts[4])
    horizontal = np.linalg.norm(pts[0] - pts[3])
    if horizontal == 0:
        return 0.0
    return float((vertical_1 + vertical_2) / (2.0 * horizontal))


def average_ear(landmarks: np.ndarray) -> float:
    """EAR averaged over both eyes."""
    left = eye_aspect_ratio(landmarks[LEFT_EYE])
    right = eye_aspect_ratio(landmarks[RIGHT_EYE])
    return (left + right) / 2.0


def mouth_aspect_ratio(landmarks: np.ndarray) -> float:
    """Vertical mouth opening divided by mouth width. Large values mean a yawn."""
    left, right, top, bottom = (landmarks[i] for i in MOUTH)
    width = np.linalg.norm(left - right)
    if width == 0:
        return 0.0
    return float(np.linalg.norm(top - bottom) / width)
