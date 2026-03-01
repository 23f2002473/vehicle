"""
svams/backend/vision/plate_detector.py

License Plate Detection Pipeline:
  1. YOLO (YOLOv8n) — detects license plate bounding boxes
  2. EasyOCR         — reads text from the cropped plate region
  3. Normalizer      — cleans/standardizes the plate string

This module is imported by the webcam capture loop and the
Flask /api/stream/frame endpoint.
"""

import re
import cv2
import numpy as np

try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False
    print("[WARN] ultralytics not installed — YOLO disabled.")

try:
    import easyocr
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    print("[WARN] easyocr not installed — OCR disabled.")


# ── Constants ────────────────────────────────────────────────
PLATE_CONF_THRESHOLD = 0.45   # YOLO minimum confidence to accept a detection
OCR_CONF_THRESHOLD   = 0.60   # EasyOCR minimum confidence
PLATE_PATTERN        = re.compile(r"^[A-Z0-9]{4,12}$")   # basic sanity check


class PlateDetector:
    """
    Wraps YOLOv8 + EasyOCR into a single callable detector.

    Usage:
        detector = PlateDetector()
        results  = detector.process_frame(bgr_frame)
        # results → list of dicts:
        # [{ plate, confidence, bbox, crop_path }, ...]
    """

    def __init__(
        self,
        yolo_model: str = "yolov8n.pt",   # swap for a custom plate-trained model
        ocr_languages: list = None,
        gpu: bool = False,
    ):
        self.gpu = gpu
        self._yolo  = None
        self._ocr   = None

        if YOLO_AVAILABLE:
            print(f"[VISION] Loading YOLO model: {yolo_model}")
            self._yolo = YOLO(yolo_model)
            print("[VISION] YOLO ready.")

        if OCR_AVAILABLE:
            langs = ocr_languages or ["en"]
            print(f"[VISION] Loading EasyOCR (langs={langs}) ...")
            self._ocr = easyocr.Reader(langs, gpu=gpu, verbose=False)
            print("[VISION] EasyOCR ready.")

    # ── Public API ────────────────────────────────────────────
    def process_frame(self, frame: np.ndarray) -> list[dict]:
        """
        Run full detection pipeline on a single BGR frame.

        Returns list of detections:
        [
          {
            "plate":      "MH12AB1234",  # normalized plate string
            "raw_ocr":    "MH 12 AB 1234",
            "confidence": 87.5,           # EasyOCR confidence 0-100
            "bbox":       (x1, y1, x2, y2),
            "crop":       np.ndarray,     # cropped plate image
          },
          ...
        ]
        """
        if self._yolo is None or self._ocr is None:
            return []

        detections = []

        # ── Step 1: YOLO detection ────────────────────────────
        yolo_results = self._yolo(frame, verbose=False)

        for result in yolo_results:
            for box in result.boxes:
                yolo_conf = float(box.conf[0])
                if yolo_conf < PLATE_CONF_THRESHOLD:
                    continue

                x1, y1, x2, y2 = map(int, box.xyxy[0])

                # Guard against out-of-bounds
                h, w = frame.shape[:2]
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(w, x2), min(h, y2)

                crop = frame[y1:y2, x1:x2]
                if crop.size == 0:
                    continue

                # ── Step 2: Preprocess crop ───────────────────
                processed = self._preprocess(crop)

                # ── Step 3: EasyOCR ───────────────────────────
                ocr_results = self._ocr.readtext(processed)
                if not ocr_results:
                    continue

                # Pick highest-confidence text block
                best = max(ocr_results, key=lambda r: r[2])
                raw_text, ocr_conf = best[1], float(best[2]) * 100

                if ocr_conf < (OCR_CONF_THRESHOLD * 100):
                    continue

                # ── Step 4: Normalize ─────────────────────────
                normalized = self._normalize(raw_text)
                if not normalized:
                    continue

                detections.append({
                    "plate":      normalized,
                    "raw_ocr":    raw_text,
                    "confidence": round(ocr_conf, 2),
                    "bbox":       (x1, y1, x2, y2),
                    "crop":       crop,
                })

        return detections

    def annotate_frame(self, frame: np.ndarray, detections: list[dict]) -> np.ndarray:
        """
        Draw bounding boxes + plate text onto a frame copy.
        Returns annotated BGR frame.
        """
        out = frame.copy()
        for det in detections:
            x1, y1, x2, y2 = det["bbox"]
            plate = det["plate"]
            conf  = det["confidence"]
            color = (34, 197, 94)   # green

            cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)
            label = f"{plate}  {conf:.0f}%"
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
            cv2.rectangle(out, (x1, y1 - th - 10), (x1 + tw + 6, y1), color, -1)
            cv2.putText(out, label, (x1 + 3, y1 - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)
        return out

    # ── Private helpers ───────────────────────────────────────
    @staticmethod
    def _preprocess(crop: np.ndarray) -> np.ndarray:
        """
        Sharpen and binarize the plate crop to help OCR accuracy.
        """
        # Upscale small plates
        h, w = crop.shape[:2]
        if w < 200:
            scale = 200 / w
            crop = cv2.resize(crop, (int(w * scale), int(h * scale)),
                              interpolation=cv2.INTER_CUBIC)

        gray    = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)
        sharp   = cv2.addWeighted(gray, 1.5, blurred, -0.5, 0)
        _, bw   = cv2.threshold(sharp, 0, 255,
                                cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return bw

    @staticmethod
    def _normalize(raw: str) -> str | None:
        """
        Strip spaces/special chars, uppercase, validate pattern.
        """
        cleaned = re.sub(r"[^A-Z0-9]", "", raw.upper())
        if PLATE_PATTERN.match(cleaned):
            return cleaned
        return None
