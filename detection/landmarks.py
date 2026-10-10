"""Face landmark detection with MediaPipe Face Mesh."""
from __future__ import annotations

import cv2
import numpy as np


class FaceLandmarker:
    """Returns face landmarks in pixel coordinates for one frame at a time."""

    def __init__(self) -> None:
        import mediapipe as mp  # imported here so tests do not need MediaPipe

        self._mesh = mp.solutions.face_mesh.FaceMesh(
            max_num_faces=1,
            refine_landmarks=True,        # adds iris points, improves eye accuracy
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )

    def detect(self, frame_bgr: np.ndarray) -> np.ndarray | None:
        """Return an (N, 2) float array of pixel coordinates, or None if no face."""
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        result = self._mesh.process(rgb)
        if not result.multi_face_landmarks:
            return None
        h, w = frame_bgr.shape[:2]
        points = result.multi_face_landmarks[0].landmark
        return np.array([[p.x * w, p.y * h] for p in points], dtype=np.float32)

    def close(self) -> None:
        self._mesh.close()
