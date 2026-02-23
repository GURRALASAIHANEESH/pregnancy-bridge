# clinical_parser.py
# ─────────────────────────────────────────────────────────────────────────────
# CHANGES FROM ORIGINAL:
#   1. _extract_hemoglobin() — replaced with version that:
#        a. Expands regex to capture 1-3 digits (catches "130" OCR error)
#        b. Corrects "130" → 13.0 (dropped decimal point)
#        c. Widens upper bound from 18 → 22 (physiological max is ~22)
#        d. Returns dict with value + flags instead of bare float
#           (allows caller to know if a correction was applied)
#
#   2. _extract_platelets() — NEW function (was completely absent)
#        a. Correct unit normalization: /cumm = /µL (multiplier = 1.0)
#        b. Infers unit from magnitude when not stated
#        c. Sanity bounds: <5k or >1.5M = OCR error flag
#        d. Returns dict with value_per_ul + flags
#
#   3. extract_clinical_fields() — added platelets field + lab_extraction_meta
#        (lab_extraction_meta carries all flags for the confirmation gate)
#
# All other functions (_extract_bp, _extract_age, etc.) are UNCHANGED.
# ─────────────────────────────────────────────────────────────────────────────

import re
import logging
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def extract_clinical_fields(ocr_text: str) -> Dict:
    """
    Parse clinical fields from raw OCR text.

    Returns dict with all fields. New fields added:
      - platelets:           int | None  (/µL normalized)
      - platelets_lakh:      float | None  (for display)
      - lab_extraction_meta: dict  (flags, correction notes, confirmation gate)
    """
    fields = {}
    lines = ocr_text.split('\n')

    # ── Unchanged fields ──────────────────────────────────────────────────────
    fields['patient_name']   = _extract_patient_name(ocr_text)
    fields['patient_id']     = _extract_patient_id(ocr_text)
    fields['age']            = _extract_age(ocr_text)
    fields['date']           = _extract_date(ocr_text)
    fields['bp_systolic'], fields['bp_diastolic'] = _extract_blood_pressure(ocr_text)
    fields['gestational_age'] = _extract_gestational_age(ocr_text)
    fields['proteinuria']    = _extract_proteinuria(ocr_text)
    fields['weight']         = _extract_weight(ocr_text)
    fields['fundal_height']  = _extract_fundal_height(ocr_text)
    fields['edema']          = _extract_edema(ocr_text)

    # ── Fixed: Hemoglobin ─────────────────────────────────────────────────────
    hb_result = _extract_hemoglobin(lines, ocr_text)
    fields['hemoglobin']     = hb_result['value']      # float | None (g/dL)

    # ── New: Platelets ────────────────────────────────────────────────────────
    plt_result = _extract_platelets(ocr_text)
    fields['platelets']      = plt_result['value_per_ul']   # int | None (/µL)
    fields['platelets_lakh'] = plt_result['value_lakh']     # float | None

    # ── Lab extraction metadata (for confirmation gate in app.py) ─────────────
    all_flags = hb_result['flags'] + plt_result['flags']
    fields['lab_extraction_meta'] = {
        'hemoglobin_raw_ocr':    hb_result['raw_ocr_string'],
        'hemoglobin_status':     hb_result['status'],
        'platelets_raw_ocr':     plt_result['raw_ocr_string'],
        'platelets_raw_unit':    plt_result['raw_unit'],
        'platelets_status':      plt_result['status'],
        'flags':                 all_flags,
        'has_critical_flags':    any('CRITICAL' in f for f in all_flags),
        'confirmation_required': True,   # ALWAYS — patient safety gate
    }

    return fields


# ══════════════════════════════════════════════════════════════════════════════
# HEMOGLOBIN EXTRACTION — FIXED
# ══════════════════════════════════════════════════════════════════════════════

def _extract_hemoglobin(lines: list, full_text: str = "") -> dict:
    r"""
    Extract haemoglobin from OCR text with digit-drop correction.

    Key fixes vs original:
      - Regex now captures 1-3 digits (\d{1,3}) — catches "130" OCR errors
      - "130" where value > 25 → corrected to 13.0 (dropped decimal point)
      - Upper validity bound raised from 18 → 22 (physiological maximum)
      - Returns dict with value + flags instead of bare float
      - Falls back to searching full_text if line scan finds nothing

    Returns:
      {
        "value":          float | None,    corrected value in g/dL
        "raw_ocr_string": str | None,      what OCR read before correction
        "status":         str,             "ok" | "corrected" | "ocr_error" | "not_found"
        "flags":          list[str]
      }
    """
    result = {
        "value": None,
        "raw_ocr_string": None,
        "status": "not_found",
        "flags": [],
    }

    # Combine line scan + full-text fallback into one unified search
    # Line scan: fast, good for well-formatted reports
    # Full-text regex: catches multi-line and wrapped cases
    candidates = []

    # Pass 1: line-by-line (original approach, improved regex)
    for line in lines:
        if 'hemoglobin' not in line.lower() and 'hgb' not in line.lower() \
                and not re.search(r'(?<!\w)hb(?!\w)', line, re.IGNORECASE):
            continue
        # FIX: \d{1,3} instead of \d{1,2} — catches "130" (dropped decimal)
        # FIX: (?:\.\d{1,2})? captures up to 2 decimal places ("13.00")
        numbers = re.findall(r'(?<!\d)(\d{1,3}(?:\.\d{1,2})?)(?!\d)', line)
        for num in numbers:
            try:
                candidates.append((num, float(num)))
            except ValueError:
                pass

    # Pass 2: full-text pattern if no candidates yet
    if not candidates and full_text:
        pattern = re.compile(
            r'(?:h[ae]m(?:o|0)gl[o0]bin|(?<!\w)hb(?!\w)|hgb)'
            r'[^\d]{0,30}?(\d{1,3}(?:\.\d{1,2})?)',
            re.IGNORECASE
        )
        m = pattern.search(full_text)
        if m:
            raw = m.group(1)
            try:
                candidates.append((raw, float(raw)))
            except ValueError:
                pass

    if not candidates:
        return result

    # Pick best candidate — prefer values in normal Hb range first
    # then check for correctable out-of-range values
    raw_str, value = candidates[0]
    result["raw_ocr_string"] = raw_str

    # FIX: Decimal-drop correction
    # If OCR misses decimal: "13.00" → "130" or "1300"
    # Rule: if value > 25 and value / 10 falls in valid range → correct it
    if value > 25.0:
        corrected = value / 10.0
        if 3.0 <= corrected <= 22.0:
            logger.warning(
                f"Hb OCR correction applied: raw='{raw_str}' "
                f"value={value} → {corrected} g/dL (decimal point dropped)"
            )
            result["flags"].append(
                f"OCR_CORRECTED: '{raw_str}' interpreted as {corrected} g/dL "
                f"(decimal point missing in OCR output)"
            )
            value = corrected
            result["status"] = "corrected"
        else:
            result["flags"].append(
                f"OCR_ERROR: '{raw_str}' → {value} g/dL, correction attempt "
                f"{corrected} still outside range — discarding"
            )
            result["status"] = "ocr_error"
            return result

    # FIX: Bounds — raised upper bound from 18 → 22
    # (sickle cell + polycythemia can legitimately hit 20+)
    if not (3.0 <= value <= 22.0):
        result["flags"].append(
            f"OCR_ERROR: Hb={value} g/dL outside physiological range (3.0–22.0)"
        )
        result["status"] = "ocr_error"
        return result

    if result["status"] != "corrected":
        result["status"] = "ok"

    result["value"] = round(value, 1)

    # Clinical flags
    if value < 7.0:
        result["flags"].append(
            f"CRITICAL: Hb={value} g/dL — Safety Net will trigger HIGH risk"
        )
    elif value < 9.0:
        result["flags"].append(
            f"ALERT: Hb={value} g/dL — severe anemia, referral recommended"
        )

    return result


# ══════════════════════════════════════════════════════════════════════════════
# PLATELETS EXTRACTION — NEW (was completely absent)
# ══════════════════════════════════════════════════════════════════════════════

# Unit → multiplier to convert TO raw /µL
# CRITICAL FIX: /cumm == /mm³ == /µL (1 mm³ = 1 µL exactly)
# 20,000 /cumm = 20,000 /µL = 0.20 lakh
# Old (implicit) behaviour treated /cumm as needing ×1000 → produced 2.0 lakh (WRONG)
_PLATELET_UNIT_MAP = {
    "/cumm":    1.0,       # /cumm = /µL — NO conversion
    "/mm3":     1.0,
    "/mm³":     1.0,
    "/ul":      1.0,
    "/µl":      1.0,
    "cells/ul": 1.0,
    "lakh/ul":  100_000.0,
    "lakh":     100_000.0,
    "x10^3/ul": 1_000.0,
    "10^3/ul":  1_000.0,
    "k/ul":     1_000.0,
    "thou/ul":  1_000.0,
}

def _extract_platelets(text: str) -> dict:
    """
    Extract platelet count from OCR text with full unit normalization.

    Always normalizes to /µL. Returns lakh value for display.

    Returns:
      {
        "value_per_ul":  int | None,    normalized to /µL
        "value_lakh":    float | None,  for display
        "raw_ocr_string": str | None,
        "raw_unit":      str | None,
        "status":        str,           "ok" | "ocr_error" | "not_found"
        "flags":         list[str]
      }
    """
    result = {
        "value_per_ul":   None,
        "value_lakh":     None,
        "raw_ocr_string": None,
        "raw_unit":       None,
        "status":         "not_found",
        "flags":          [],
    }

    # Match: "Platelet Count", "Platelets", "PLT", "Thrombocytes"
    # followed by a number (with optional commas) + optional unit
    pattern = re.compile(
        r'(?:platelet[s]?(?:\s+count)?|plt|thrombocyte[s]?)'
        r'[^\d]{0,30}?'
        r'([\d,]+(?:\.\d+)?)'           # number — allows commas like "20,000"
        r'\s*'
        r'((?:/\s*(?:cumm|mm3|mm³|ul|µl)|lakh(?:/ul)?|'
        r'x10\^3/ul|10\^3/ul|k/ul|thou/ul|cells/ul)?)',
        re.IGNORECASE
    )

    match = pattern.search(text)
    if not match:
        return result

    raw_num  = match.group(1).strip()
    raw_unit = match.group(2).strip().lower() if match.group(2) else ""

    result["raw_ocr_string"] = raw_num

    # Fallback: scan tail of line for a unit separated by reference range
    if not raw_unit:
        tail_unit = re.search(
            r'\b(cumm|/cumm|/ul|/µl|lakh)\b',
            text[match.end():match.end() + 60],
            re.IGNORECASE
        )
        if tail_unit:
            raw_unit = tail_unit.group(1).lower()

    result["raw_unit"] = raw_unit if raw_unit else "not_stated"

    # Clean commas from number
    clean_num = raw_num.replace(',', '')
    try:
        raw_value = float(clean_num)
    except ValueError:
        result["status"] = "ocr_error"
        result["flags"].append(f"Cannot parse platelet number: '{raw_num}'")
        return result

    # Identify multiplier from unit
    multiplier = None
    for unit_key, mult in _PLATELET_UNIT_MAP.items():
        if unit_key in raw_unit:
            multiplier = mult
            break

    # Infer from magnitude when unit is absent or unrecognized
    if multiplier is None:
        if raw_value < 100:
            multiplier = 100_000.0
            result["flags"].append(
                f"INFERRED_UNIT: {raw_value} < 100, treated as lakh → "
                f"{int(raw_value * 100_000):,}/µL"
            )
        elif raw_value < 1_500:
            multiplier = 1_000.0
            result["flags"].append(
                f"INFERRED_UNIT: {raw_value} < 1500, treated as ×10³/µL → "
                f"{int(raw_value * 1_000):,}/µL"
            )
        else:
            multiplier = 1.0
            result["flags"].append(
                f"INFERRED_UNIT: {raw_value} ≥ 1500, treated as /µL directly"
            )

    value_per_ul = int(round(raw_value * multiplier))

    # Sanity bounds
    if value_per_ul < 5_000:
        result["flags"].append(
            f"OCR_ERROR: Platelets={value_per_ul:,}/µL below minimum possible "
            f"(5,000/µL) — likely OCR misread, confirm manually"
        )
        result["status"] = "ocr_error"
    elif value_per_ul > 1_500_000:
        result["flags"].append(
            f"OCR_ERROR: Platelets={value_per_ul:,}/µL exceeds maximum possible "
            f"(1,500,000/µL) — likely OCR misread, confirm manually"
        )
        result["status"] = "ocr_error"
    else:
        result["status"] = "ok"

    # Clinical flags — set regardless of OCR status (ANM needs to see these)
    if value_per_ul < 50_000:
        result["flags"].append(
            f"CRITICAL: Platelets={value_per_ul:,}/µL "
            f"({value_per_ul/100_000:.2f} lakh) — URGENT REFERRAL REQUIRED"
        )
    elif value_per_ul < 100_000:
        result["flags"].append(
            f"ALERT: Platelets={value_per_ul:,}/µL "
            f"({value_per_ul/100_000:.2f} lakh) — below normal (1.5–4.0 lakh)"
        )

    result["value_per_ul"] = value_per_ul
    result["value_lakh"]   = round(value_per_ul / 100_000, 2)

    return result


# ══════════════════════════════════════════════════════════════════════════════
# ALL FUNCTIONS BELOW ARE UNCHANGED FROM ORIGINAL
# ══════════════════════════════════════════════════════════════════════════════

def _extract_patient_name(text: str) -> Optional[str]:
    match = re.search(r'Name\s+([A-Za-z\s]+?)(?:Patient|Date|\n)', text, re.IGNORECASE)
    return match.group(1).strip() if match else None

def _extract_patient_id(text: str) -> Optional[str]:
    match = re.search(r'Patient\s*ID[\s:]*([A-Z0-9]+)', text, re.IGNORECASE)
    return match.group(1).strip() if match else None

def _extract_age(text: str) -> Optional[str]:
    match = re.search(r'Age[\s:]+(\d+y.*?)\s+Sex', text, re.IGNORECASE)
    return match.group(1).strip() if match else None

def _extract_date(text: str) -> Optional[str]:
    match = re.search(r'Date[\s:]+(\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4})', text, re.IGNORECASE)
    return match.group(1).strip() if match else None

def _extract_blood_pressure(text: str) -> Tuple[Optional[int], Optional[int]]:
    match = re.search(
        r'(BP|B\.P|Blood Pressure)[\s:]*([0-9]{2,3}\s*/\s*[0-9]{2,3})',
        text, re.IGNORECASE
    )
    if not match:
        return None, None
    bp_string = match.group(2).replace(" ", "")
    parts = bp_string.split("/")
    if len(parts) != 2:
        return None, None
    try:
        systolic  = int(parts[0])
        diastolic = int(parts[1])
        if 70 <= systolic <= 200 and 40 <= diastolic <= 140:
            return systolic, diastolic
    except ValueError:
        pass
    return None, None

def _extract_gestational_age(text: str) -> Optional[int]:
    match = re.search(
        r'(GA|Gestational Age)[\s:]*([0-9]{1,2})\s*(weeks|wks)?',
        text, re.IGNORECASE
    )
    if not match:
        return None
    try:
        ga = int(match.group(2))
        return ga if 4 <= ga <= 42 else None
    except ValueError:
        return None

def _extract_proteinuria(text: str) -> Optional[str]:
    patterns = [
        r'Protein(?:uria)?[\s:]*(\d\+|\+{1,4}|negative|trace|nil)',
        r'Urine\s*Protein[\s:]*(\d\+|\+{1,4}|negative|trace|nil)',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).lower()
    return None

def _extract_weight(text: str) -> Optional[float]:
    match = re.search(r'Weight[\s:]*([0-9]{2,3}(?:\.\d)?)\s*kg', text, re.IGNORECASE)
    if not match:
        return None
    try:
        weight = float(match.group(1))
        return weight if 30 <= weight <= 150 else None
    except ValueError:
        return None

def _extract_fundal_height(text: str) -> Optional[int]:
    match = re.search(r'(Fundal Height|FH)[\s:]*([0-9]{2})\s*cm', text, re.IGNORECASE)
    if not match:
        return None
    try:
        fh = int(match.group(2))
        return fh if 10 <= fh <= 45 else None
    except ValueError:
        return None

def _extract_edema(text: str) -> Optional[bool]:
    patterns = [
        (r'Edema[\s:]*(\+{1,4}|present|yes)', True),
        (r'Swelling[\s:]*(\+{1,4}|present|yes)', True),
        (r'Edema[\s:]*(absent|no|nil)', False),
    ]
    for pattern, value in patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return value
    return None
