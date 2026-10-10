import numpy as np
import pytest

from detection.metrics import (
    LEFT_EYE,
    MOUTH,
    RIGHT_EYE,
    average_ear,
    eye_aspect_ratio,
    mouth_aspect_ratio,
)

N_LANDMARKS = 478


def eye_points(opening: float) -> np.ndarray:
    """Six points p1..p6 for an eye 10 px wide with the given half-opening."""
    return np.array([
        [0, 0],                 # p1 left corner
        [3, opening],           # p2 upper lid
        [7, opening],           # p3 upper lid
        [10, 0],                # p4 right corner
        [7, -opening],          # p5 lower lid
        [3, -opening],          # p6 lower lid
    ], dtype=float)


def landmarks_with_eyes(opening: float) -> np.ndarray:
    lm = np.zeros((N_LANDMARKS, 2), dtype=float)
    lm[LEFT_EYE] = eye_points(opening)
    lm[RIGHT_EYE] = eye_points(opening)
    return lm


def test_ear_open_eye():
    # vertical sums: 2*opening each -> (4 + 4) / (2 * 10) = 0.4
    assert eye_aspect_ratio(eye_points(2.0)) == pytest.approx(0.4)


def test_ear_closed_eye_is_small():
    assert eye_aspect_ratio(eye_points(0.5)) == pytest.approx(0.1)


def test_average_ear_uses_both_eyes():
    assert average_ear(landmarks_with_eyes(2.0)) == pytest.approx(0.4)


def test_ear_zero_width_returns_zero():
    pts = np.zeros((6, 2))
    assert eye_aspect_ratio(pts) == 0.0


def test_mar_closed_mouth_is_small():
    lm = np.zeros((N_LANDMARKS, 2))
    left, right, top, bottom = MOUTH
    lm[left] = [0, 0]
    lm[right] = [10, 0]
    lm[top] = [5, -0.5]
    lm[bottom] = [5, 0.5]
    assert mouth_aspect_ratio(lm) == pytest.approx(0.1)


def test_mar_open_mouth_is_large():
    lm = np.zeros((N_LANDMARKS, 2))
    left, right, top, bottom = MOUTH
    lm[left] = [0, 0]
    lm[right] = [10, 0]
    lm[top] = [5, -3]
    lm[bottom] = [5, 3]
    assert mouth_aspect_ratio(lm) == pytest.approx(0.6)
