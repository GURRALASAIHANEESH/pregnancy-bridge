"""
ocr_utils.py — PregnancyBridge OCR Extraction Layer
====================================================

FIXES in this version:
1. Adaptive thresholding replaces flat contrast enhancement
   — suppresses watermark grey ink, preserves dark report text
2. Watermark suppression via top-hat morphological filter
3. Correct PSM mode for lab report tables (--psm 4)
4. extract_lab_values() — parses Hb + platelets with:
   a. Correct unit normalization (/cumm == /µL, no multiplication)
   b. OCR digit correction (e.g. "130" → 13.0 for Hb)
   c. Hard sanity bounds — flags impossible values as OCR errors
   d. Returns confirmation_required=True always (patient safety gate)

Interface preserved:
  perform_ocr(image_path) → str              (unchanged)
  preprocess_image(image_path) → PIL.Image   (enhanced)
  extract_lab_values(text) → dict            (NEW — used by clinical_parser)
"""

import re
import logging
from pathlib import Path
from typing import Optional

import pytesseract
from PIL import Image, ImageEnhance, ImageFilter

logger = logging.getLogger(__name__)

pytesseract.pytesseract.tesseract_cmd = (
    r"C:\Users\gurra\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"
)

# ── OpenCV import (optional — graceful fallback to PIL-only if not installed) ──
try:
    import cv2
    import numpy as np
    _CV2_AVAILABLE = True
except ImportError:
    _CV2_AVAILABLE = False
    logger.warning(
        "opencv-python not installed. Watermark suppression disabled. "
        "Run: pip install opencv-python"
    )


# ══════════════════════════════════════════════════════════════════════════════
# IMAGE PREPROCESSING
# ══════════════════════════════════════════════════════════════════════════════

def preprocess_image(image_path: str) -> Optional[Image.Image]:
    """
    Preprocess lab report image for maximum OCR accuracy.

    Pipeline:
      1. Upscale ×2 (Tesseract needs ≥300 DPI equivalent)
      2. Grayscale
      3. If OpenCV available:
           a. Top-hat transform — removes light watermark ink
           b. Adaptive threshold (Gaussian) — binarises to black/white
              This crushes grey watermark text to white while keeping
              dark printed text black.
      4. If OpenCV NOT available:
           PIL contrast enhance only (original behaviour, no regression)
    """
    if not Path(image_path).exists():
        logger.error(f"Image not found: {image_path}")
        return None

    try:
        img = Image.open(image_path)

        # Step 1: Upscale before any processing (improves Tesseract accuracy)
        width, height = img.size
        img = img.resize((width * 2, height * 2), Image.Resampling.LANCZOS)

        # Step 2: Grayscale
        img = img.convert('L')

        if _CV2_AVAILABLE:
            # Step 3a: Convert PIL → numpy for OpenCV processing
            img_np = np.array(img)

            # Step 3b: Top-hat morphological filter
            # Removes bright (light-grey) watermark patterns from background
            # kernel size 25×25 works well for typical pathology report watermarks
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 25))
            tophat = cv2.morphologyEx(img_np, cv2.MORPH_TOPHAT, kernel)
            img_np = cv2.add(img_np, tophat)

            # Step 3c: Adaptive Gaussian threshold
            # blockSize=15, C=8 — tuned for lab report text on white/grey bg
            # Converts grey watermark ink → white (255), dark text → black (0)
            img_np = cv2.adaptiveThreshold(
                img_np,
                maxValue=255,
                adaptiveMethod=cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                thresholdType=cv2.THRESH_BINARY,
                blockSize=15,
                C=8,
            )

            # Step 3d: Light dilation to reconnect broken digit strokes
            # (OCR digit '3' vs '2' confusion is partly from broken strokes)
            dilate_kernel = np.ones((2, 2), np.uint8)
            img_np = cv2.dilate(img_np, dilate_kernel, iterations=1)

            # Convert back to PIL
            img = Image.fromarray(img_np)
            logger.debug("Preprocessing: OpenCV adaptive threshold applied")

        else:
            # Fallback: PIL-only path
            # Do NOT use contrast.enhance(2.0) — it amplifies watermarks
            # Use a gentle sharpen only
            img = img.filter(ImageFilter.SHARPEN)
            logger.debug("Preprocessing: PIL-only fallback (no watermark suppression)")

        return img

    except Exception as e:
        logger.error(f"Image preprocessing failed: {e}")
        return None


def perform_ocr(image_path: str) -> str:
    """
    Run Tesseract OCR on a lab report image.

    PSM mode:
      --psm 4  = "Assume a single column of text of variable sizes"
      Better than --psm 6 for multi-column lab report tables.
      Falls back to --psm 6 if psm 4 gives empty output.
    """
    img = preprocess_image(image_path)
    if img is None:
        return ""

    try:
        # PSM 4 — best for columnar lab reports
        text = pytesseract.image_to_string(
            img,
            config='--psm 4 --oem 3 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz/.,:-+() '
        )

        if not text.strip():
            # Fallback to PSM 6 if PSM 4 gives nothing
            logger.warning("PSM 4 gave empty output, retrying with PSM 6")
            text = pytesseract.image_to_string(img, config='--psm 6')

        logger.debug(f"OCR extracted {len(text)} characters")
        return text

    except Exception as e:
        logger.error(f"OCR failed: {e}")
        return ""


# ══════════════════════════════════════════════════════════════════════════════
# LAB VALUE EXTRACTION + UNIT NORMALIZATION + SANITY BOUNDS
# ══════════════════════════════════════════════════════════════════════════════

# ── Physiological bounds (hard limits) ────────────────────────────────────────
HB_BOUNDS = {
    "impossible_low":  3.0,     # Below this: OCR error, reject
    "impossible_high": 22.0,    # Above this: OCR error, reject
    "critical_low":    7.0,     # Matches Safety Net threshold → HIGH risk
    "severe_low":      9.0,     # Severe anemia threshold
}

PLATELET_BOUNDS = {
    "impossible_low":    5_000,      # Below this: almost certainly OCR error
    "impossible_high": 1_500_000,    # Above this: OCR error
    "critical_low":     50_000,      # < 50k → CRITICAL, urgent referral
    "low_threshold":   100_000,      # < 100k → flag for review
}

# ── Platelet unit → multiplier to convert TO raw /µL count ───────────────────
# KEY FIX: /cumm == /mm³ == /µL  (1 mm³ = 1 µL exactly)
# Therefore /cumm needs NO conversion — multiplier is 1.0
PLATELET_UNIT_MULTIPLIERS = {
    "/cumm":     1.0,       # /cumm = /µL — NO conversion needed
    "/mm3":      1.0,       # same
    "/mm³":      1.0,       # unicode variant
    "/ul":       1.0,       # already /µL
    "/µl":       1.0,
    "cells/ul":  1.0,
    "cells/µl":  1.0,
    "lakh/ul":   100_000.0, # lakh → raw count
    "lakh":      100_000.0,
    "x10^3/ul":  1_000.0,   # thousands notation
    "k/ul":      1_000.0,
    "10^3/ul":   1_000.0,
    "thou/ul":   1_000.0,
}


def _parse_hb(text: str) -> dict:
    """
    Extract haemoglobin value from OCR text with digit correction.

    Common OCR errors on lab reports with watermarks:
      "13.00" → "12.1"  (3→2 misread, trailing 0 dropped)
      "130"   → should be 13.0 (decimal point lost)
      "7 0"   → should be 7.0  (space inserted in decimal)

    Returns:
      {
        "raw_ocr_string": str,      # what OCR actually read
        "value": float | None,      # corrected value in g/dL
        "status": "ok" | "corrected" | "ocr_error" | "not_found",
        "flags": list[str]          # clinical flags
      }
    """
    result = {
        "raw_ocr_string": None,
        "value": None,
        "status": "not_found",
        "flags": [],
    }

    # Pattern: "Hemoglobin", "Hb", "HGB", "Haemoglobin" + optional junk + number
    # Handles: 13.00, 13.0, 130, 7 0, 12.1
    pattern = re.compile(
        r'(?:h[ae]m(?:o|0)gl[o0]bin|(?<!\w)hb(?!\w)|hgb)[^\d]{0,30}?'
        r'(\d{1,3}(?:[.\s]\d{1,2})?)',
        re.IGNORECASE
    )

    match = pattern.search(text)
    if not match:
        return result

    raw = match.group(1).strip()
    result["raw_ocr_string"] = raw

    # Normalize spaces acting as decimal points: "7 0" → "7.0"
    normalized = re.sub(r'(\d)\s+(\d)', r'\1.\2', raw)

    try:
        value = float(normalized)
    except ValueError:
        result["status"] = "ocr_error"
        result["flags"].append(f"Cannot parse Hb value: '{raw}'")
        return result

    # Digit correction: if value > 25, likely a decimal point was dropped
    # e.g. "130" OCR misread of "13.0"
    if value > 25.0:
        corrected = value / 10.0
        logger.warning(
            f"Hb OCR correction: {value} → {corrected} g/dL "
            f"(decimal point likely dropped by OCR)"
        )
        result["flags"].append(f"OCR_CORRECTED: {value} interpreted as {corrected} g/dL")
        value = corrected
        result["status"] = "corrected"
    else:
        result["status"] = "ok"

    # Sanity bounds check
    if value < HB_BOUNDS["impossible_low"] or value > HB_BOUNDS["impossible_high"]:
        result["flags"].append(
            f"OCR_ERROR: Hb={value} outside physiological range "
            f"({HB_BOUNDS['impossible_low']}–{HB_BOUNDS['impossible_high']} g/dL)"
        )
        result["status"] = "ocr_error"
        result["value"] = None  # Do NOT use this value
        return result

    result["value"] = round(value, 1)

    # Clinical flags
    if value < HB_BOUNDS["critical_low"]:
        result["flags"].append(f"CRITICAL: Hb={value} g/dL — severe anemia, Safety Net triggers HIGH risk")
    elif value < HB_BOUNDS["severe_low"]:
        result["flags"].append(f"ALERT: Hb={value} g/dL — severe anemia threshold")

    return result


def _parse_platelets(text: str) -> dict:
    """
    Extract platelet count from OCR text with unit normalization.

    CRITICAL FIX — Unit math:
      /cumm = /mm³ = /µL  (these are the SAME unit, 1 mm³ = 1 µL)
      20,000 /cumm = 20,000 /µL = 0.20 lakh
      The old code was treating /cumm as needing ×1000 conversion → WRONG

    Returns:
      {
        "raw_ocr_string": str,
        "raw_unit": str | None,
        "value_per_ul": int | None,   # normalized to /µL
        "value_lakh": float | None,   # in lakh (for display)
        "status": "ok" | "ocr_error" | "not_found",
        "flags": list[str]
      }
    """
    result = {
        "raw_ocr_string": None,
        "raw_unit": None,
        "value_per_ul": None,
        "value_lakh": None,
        "status": "not_found",
        "flags": [],
    }

    # Pattern: "Platelet", "PLT", "Thrombocytes" + number + optional unit
    pattern = re.compile(
        r'(?:platelet[s]?(?:\s+count)?|plt|thrombocyte[s]?)[^\d]{0,30}?'
        r'([\d,.\s]+?)'                          # number (may have commas)
        r'\s*'
        r'((?:/|x|×)?(?:cumm|mm3|mm³|ul|µl|lakh|thou|k/ul|10\^3[/\s]?ul|cells[/\s]?ul)?)',
        re.IGNORECASE
    )

    match = pattern.search(text)
    if not match:
        return result

    raw_num = match.group(1).strip()
    raw_unit = match.group(2).strip().lower() if match.group(2) else ""

    result["raw_ocr_string"] = raw_num
    result["raw_unit"] = raw_unit

    # Clean number: remove commas and spaces
    clean_num = re.sub(r'[,\s]', '', raw_num)

    try:
        raw_value = float(clean_num)
    except ValueError:
        result["status"] = "ocr_error"
        result["flags"].append(f"Cannot parse platelet value: '{raw_num}'")
        return result

    # Identify unit multiplier
    multiplier = None
    for unit_key, mult in PLATELET_UNIT_MULTIPLIERS.items():
        if unit_key in raw_unit:
            multiplier = mult
            break

    # If no unit found, infer from value magnitude
    if multiplier is None:
        if raw_value < 100:
            # Probably in lakh (e.g. "2.3 lakh" written without unit)
            multiplier = 100_000.0
            result["flags"].append(f"INFERRED_UNIT: value={raw_value} < 100, treated as lakh")
        elif raw_value < 1500:
            # Probably in thousands (e.g. "150" meaning 150×10³)
            multiplier = 1_000.0
            result["flags"].append(f"INFERRED_UNIT: value={raw_value} < 1500, treated as ×10³/µL")
        else:
            # Already in /µL or /cumm
            multiplier = 1.0
            result["flags"].append(f"INFERRED_UNIT: value={raw_value}, treated as /µL directly")

    # Convert to /µL
    value_per_ul = int(raw_value * multiplier)

    # Sanity bounds
    if value_per_ul < PLATELET_BOUNDS["impossible_low"]:
        result["flags"].append(
            f"OCR_ERROR: Platelets={value_per_ul}/µL is below minimum possible "
            f"({PLATELET_BOUNDS['impossible_low']}/µL) — likely OCR misread"
        )
        result["status"] = "ocr_error"
        # Still return value — let confirmation step decide
    elif value_per_ul > PLATELET_BOUNDS["impossible_high"]:
        result["flags"].append(
            f"OCR_ERROR: Platelets={value_per_ul}/µL exceeds maximum possible "
            f"({PLATELET_BOUNDS['impossible_high']}/µL) — likely OCR misread"
        )
        result["status"] = "ocr_error"
    else:
        result["status"] = "ok"

    # Clinical flags (regardless of OCR status — for ANM awareness)
    if value_per_ul < PLATELET_BOUNDS["critical_low"]:
        result["flags"].append(
            f"CRITICAL: Platelets={value_per_ul:,}/µL "
            f"({value_per_ul/100_000:.2f} lakh) — URGENT REFERRAL REQUIRED"
        )
    elif value_per_ul < PLATELET_BOUNDS["low_threshold"]:
        result["flags"].append(
            f"ALERT: Platelets={value_per_ul:,}/µL — below normal threshold (1.0 lakh)"
        )

    result["value_per_ul"] = value_per_ul
    result["value_lakh"] = round(value_per_ul / 100_000, 2)

    return result


def extract_lab_values(text: str) -> dict:
    """
    Main entry point for lab value extraction from OCR text.

    Always returns confirmation_required=True.
    Risk assessment MUST NOT run until ANM confirms these values.

    Returns:
    {
        "hemoglobin": {
            "value": float | None,          # g/dL, corrected
            "raw_ocr_string": str | None,
            "status": "ok"|"corrected"|"ocr_error"|"not_found",
            "flags": list[str]
        },
        "platelets": {
            "value_per_ul": int | None,     # normalized to /µL
            "value_lakh": float | None,     # for display
            "raw_ocr_string": str | None,
            "raw_unit": str | None,
            "status": "ok"|"ocr_error"|"not_found",
            "flags": list[str]
        },
        "confirmation_required": True,      # ALWAYS True — patient safety
        "all_flags": list[str],             # merged flags for UI display
        "has_critical_flags": bool          # True if any CRITICAL flag present
    }
    """
    hb_result = _parse_hb(text)
    plt_result = _parse_platelets(text)

    all_flags = hb_result["flags"] + plt_result["flags"]
    has_critical = any("CRITICAL" in f for f in all_flags)

    return {
        "hemoglobin": hb_result,
        "platelets": plt_result,
        "confirmation_required": True,  # ALWAYS — non-negotiable patient safety gate
        "all_flags": all_flags,
        "has_critical_flags": has_critical,
    }
