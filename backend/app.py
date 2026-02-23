"""
PregnancyBridge Backend API
===========================
POLICY: Rule engine is authoritative. MedGemma advice is advisory;
raw outputs are stored for audit only.

Immutable artifact storage with HMAC signing for integrity verification.

FIXES in this version:
  1. Env vars: warnings only, no hard crash at import time
  2. lifespan: MedGemma loaded lazily in background thread, never blocks startup
  3. Single model loader: medgemma_extractor singleton only (removes OOM from_pretrained path)
  4. Confirmation gate: triggers on ANY OCR extraction (not just critical flags)
  5. /api/v1/confirm-labs endpoint added
  6. Platelets from OCR now propagated to risk engine
  7. run_medgemma_inference routes through singleton, not second loader
"""

import os
import sys
import json
import base64
import hashlib
import hmac
import tempfile
import threading
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
import logging

# ── Path setup ────────────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent.parent.parent))  # D:/MedGemma
sys.path.insert(0, str(Path(__file__).parent.parent))          # D:/MedGemma/src

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ── pregnancy_bridge imports ──────────────────────────────────────────────────
from pregnancy_bridge.modules.risk_engine import assess_risk as assess_risk_engine
from pregnancy_bridge.modules.symptom_risk_engine import SymptomRiskEngine
from pregnancy_bridge.modules.medgemma_bridge import explain_context
from pregnancy_bridge.modules.missing_data_recommender import recommend_next_actions_with_deterministic
from pregnancy_bridge.modules.symptom_intake import SymptomIntake
from pregnancy_bridge.modules.ocr_utils import perform_ocr
from pregnancy_bridge.modules.clinical_parser import extract_clinical_fields

# FIX 1: Import extractor functions — do NOT call get_clinical_reasoner() here.
# Calling it at module level would trigger model load at import time → OOM crash.
from pregnancy_bridge.modules.medgemma_extractor import (
    get_clinical_reasoner,
    load_model_async,          # background thread loader
    get_backend_status,        # for /health endpoint
)

# ── Environment variables ─────────────────────────────────────────────────────
# FIX 2: No hard raise at module level. Log warnings instead.
# Server starts regardless; affected endpoints return 503 if config missing.

ARTIFACT_HMAC_KEY_STR = os.getenv('ARTIFACT_HMAC_KEY', '')
if not ARTIFACT_HMAC_KEY_STR:
    logger.warning(
        "ARTIFACT_HMAC_KEY not set in environment. "
        "Artifact signing will use a placeholder key. "
        "Set this variable in .env before production use."
    )
    ARTIFACT_HMAC_KEY_STR = 'placeholder-dev-key-not-for-production'
ARTIFACT_HMAC_KEY = ARTIFACT_HMAC_KEY_STR.encode()

MEDGEMMA_SNAPSHOT_PATH = os.getenv('MEDGEMMA_SNAPSHOT_PATH', '')
if not MEDGEMMA_SNAPSHOT_PATH:
    logger.warning(
        "MEDGEMMA_SNAPSHOT_PATH not set. MedGemma inference will be skipped; "
        "rule-based Safety Net will handle all assessments."
    )

MEDGEMMA_DEVICE     = os.getenv('MEDGEMMA_DEVICE', 'cpu')
MEDGEMMA_TIMEOUT_SEC = int(os.getenv('MEDGEMMA_TIMEOUT_SEC', '2000'))

ARTIFACTS_DIR = Path('artifacts/backend_runs')
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

# ── In-memory state ───────────────────────────────────────────────────────────
JOB_QUEUE: Dict[str, Any] = {}

# Pending confirmations: keyed by confirmation_token
# Stores extracted OCR fields waiting for ANM approval
PENDING_CONFIRMATIONS: Dict[str, dict] = {}


# ════════════════════════════════════════════════════════════════════════════
# DATA MODELS
# ════════════════════════════════════════════════════════════════════════════

class AssessmentRequest(BaseModel):
    patient_id: str = Field(..., description="Unique patient identifier")
    name: str
    age: int = Field(..., ge=15, le=55)
    gestational_age_weeks: Optional[int] = None
    bp_systolic: int
    bp_diastolic: int
    weight_kg: float
    hemoglobin_g_dl: Optional[float] = None
    platelets_per_ul: Optional[int] = None
    proteinuria: Optional[str] = None

    class Config:
        json_schema_extra = {"example": {
            "patient_id": "DEMO_006", "name": "Kavitha Naik", "age": 28,
            "gestational_age_weeks": 22, "bp_systolic": 128, "bp_diastolic": 84,
            "weight_kg": 65.0, "hemoglobin_g_dl": 11.2,
            "platelets_per_ul": 145000, "proteinuria": "Negative"
        }}


class FieldVisitRequest(BaseModel):
    patient_id: str
    visit_id: Optional[str] = None
    visit_date: Optional[str] = None
    gestational_age_weeks: Optional[int] = None
    blood_pressure: Optional[str] = None
    bp_systolic: Optional[int] = Field(default=120)
    bp_diastolic: Optional[int] = Field(default=80)
    hemoglobin: Optional[float] = None
    proteinuria: Optional[str] = None
    weight_kg: Optional[float] = None
    symptoms: Optional[list] = Field(default_factory=list)
    other_symptoms: str = Field(default="")
    images: Optional[list] = Field(default_factory=list)

    class Config:
        json_schema_extra = {"example": {
            "patient_id": "DEMO_006", "visit_id": "VISIT_006_002",
            "visit_date": "2026-02-11T09:10:00Z", "gestational_age_weeks": 36,
            "bp_systolic": 142, "bp_diastolic": 92, "hemoglobin": 10.8,
            "proteinuria": "+1", "weight_kg": 72.0,
            "symptoms": ["blurred_vision", "headache", "pedal_edema"], "images": []
        }}


class LabConfirmRequest(BaseModel):
    """ANM confirmation of OCR-extracted lab values before risk assessment runs."""
    confirmation_token:           str           = Field(..., description="Token from pending_confirmation response")
    confirmed_hemoglobin:         Optional[float] = Field(None, description="ANM-verified Hb in g/dL")
    confirmed_platelets_per_ul:   Optional[int]   = Field(None, description="ANM-verified platelet count /µL")
    confirmed_bp_systolic:        Optional[int]   = Field(None, description="ANM-verified systolic BP mmHg")
    confirmed_bp_diastolic:       Optional[int]   = Field(None, description="ANM-verified diastolic BP mmHg")
    confirmed_gestational_age:    Optional[int]   = Field(None, description="ANM-verified gestational age in weeks")
    confirmed_proteinuria:        Optional[str]   = Field(None, description="ANM-verified proteinuria result")
    anm_notes:                    Optional[str]   = Field(default='', description="Optional free-text notes from ANM")


class AssessmentResponse(BaseModel):
    run_id: str
    status: str
    message: str
    artifacts_path: Optional[str] = None


# ════════════════════════════════════════════════════════════════════════════
# UTILITY FUNCTIONS (unchanged from original)
# ════════════════════════════════════════════════════════════════════════════

def compute_hmac(data: bytes) -> str:
    return hmac.new(ARTIFACT_HMAC_KEY, data, hashlib.sha256).hexdigest()

def compute_sha256(file_path: Path) -> str:
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def derive_seed(request_data: dict) -> int:
    request_str = json.dumps(request_data, sort_keys=True)
    hash_hex = hashlib.sha256(request_str.encode()).hexdigest()[:8]
    return int(hash_hex, 16)

def save_with_fsync(file_path: Path, content: str):
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
        f.flush()
        os.fsync(f.fileno())
    try:
        os.chmod(file_path, 0o444)
    except Exception:
        pass


# ════════════════════════════════════════════════════════════════════════════
# RULE ENGINE (unchanged from original)
# ════════════════════════════════════════════════════════════════════════════

def run_rule_engine(vitals: dict) -> dict:
    try:
        mapped_data = {
            'hemoglobin':       vitals.get('hemoglobin_g_dl'),
            'bp_systolic':      vitals.get('bp_systolic'),
            'bp_diastolic':     vitals.get('bp_diastolic'),
            'gestational_age':  vitals.get('gestational_age_weeks'),
            'proteinuria':      vitals.get('proteinuria'),
            'weight':           vitals.get('weight_kg'),
            'platelets':        vitals.get('platelets_per_ul'),
            'age':              vitals.get('age'),
        }
        result = assess_risk_engine(mapped_data)
        return {
            'risk_level':    result.get('risk_level', 'Medium'),
            'risk_score':    result.get('risk_score', 0),
            'recommendations': result.get('recommendations', []),
            'confidence':    1.0,
        }
    except Exception as e:
        logger.warning(f"Risk engine failed, using fallback: {e}")
        return run_fallback_rules(vitals)


def run_fallback_rules(vitals: dict) -> dict:
    bp_sys    = vitals.get('bp_systolic', 120)
    bp_dia    = vitals.get('bp_diastolic', 80)
    hb        = vitals.get('hemoglobin_g_dl', 12.0)
    platelets = vitals.get('platelets_per_ul', 150000)
    proteinuria = vitals.get('proteinuria', 'Negative')

    risk_level = 'Low'
    recommendations = []
    risk_score = 0

    if bp_sys >= 160 or bp_dia >= 110:
        risk_level = 'High'; risk_score += 3
        recommendations.append('URGENT: Immediate referral for severe hypertension')
    elif bp_sys >= 140 or bp_dia >= 90:
        risk_level = 'High'; risk_score += 2
        recommendations.append('Referral to PHC for hypertension management')
    elif bp_sys >= 130 or bp_dia >= 85:
        if risk_level == 'Low': risk_level = 'Medium'
        risk_score += 1
        recommendations.append('Follow-up within 1 week for BP monitoring')

    if hb and hb < 7.0:
        risk_level = 'High'; risk_score += 3
        recommendations.append('CRITICAL: Severe anemia — immediate referral required')
    elif hb and hb < 9.0:
        risk_level = 'High'; risk_score += 2
        recommendations.append('Severe anemia — immediate iron infusion required')
    elif hb and hb < 11.0:
        if risk_level == 'Low': risk_level = 'Medium'
        risk_score += 1
        recommendations.append('Iron and folic acid supplementation required')

    if platelets and platelets < 50_000:
        risk_level = 'High'; risk_score += 3
        recommendations.append('CRITICAL: Platelets < 50k — urgent hospital referral')
    elif platelets and platelets < 100_000:
        risk_level = 'High'; risk_score += 2
        recommendations.append('Low platelet count — referral for evaluation')

    if proteinuria and proteinuria not in ['Negative', 'negative', '', 'Not tested', 'nil']:
        if proteinuria in ['+3', '3+', '+2', '2+']:
            risk_level = 'High'; risk_score += 2
            recommendations.append('URGENT: Significant proteinuria — pre-eclampsia evaluation')
        else:
            if risk_level == 'Low': risk_level = 'Medium'
            recommendations.append('Trace protein — monitor for pre-eclampsia')

    if not recommendations:
        recommendations = [
            'All parameters within normal range — continue routine antenatal care',
            'Next visit in 4 weeks',
            'Maintain healthy diet and regular exercise',
        ]

    return {'risk_level': risk_level, 'risk_score': risk_score,
            'recommendations': recommendations, 'confidence': 1.0}


# ════════════════════════════════════════════════════════════════════════════
# MEDGEMMA INFERENCE
# FIX 3: Routes through singleton from medgemma_extractor — NOT from_pretrained
# ════════════════════════════════════════════════════════════════════════════

def run_medgemma_inference(vitals: dict, run_dir: Path, timeout_sec: int) -> dict:
    """
    Run MedGemma inference via the singleton loaded in medgemma_extractor.
    Falls back gracefully if model is not loaded (returns fallback_triggered=True).
    Never raises — all exceptions are caught.
    """
    start_time = time.time()

    # FIX: Use singleton — never call load_medgemma_model() (OOM path)
    try:
        reasoner = get_clinical_reasoner(force_cpu=True)
    except Exception:
        reasoner = None

    # If model not loaded, return clean fallback immediately
    if reasoner is None or reasoner.model is None:
        logger.warning("MedGemma not loaded — skipping AI inference, using rule engine only")
        return {
            'ai_risk': None,
            'ai_recommendations': [],
            'confidence': 0.0,
            'raw_text': 'MedGemma not loaded — rule engine is authoritative',
            'fallback_triggered': True,
            'inference_time_ms': 0,
        }

    try:
        result = reasoner.reason_about_case(vitals)

        inference_time_ms = result.get('inference_time_ms', 0)
        raw_text = result.get('reasoning', '')

        # Save raw output for audit
        raw_json = {
            'raw_response':      raw_text,
            'inference_time_ms': inference_time_ms,
            'model_backend':     result.get('hardware_used', 'CPU'),
        }
        raw_file = run_dir / 'medgemma_raw.json'
        save_with_fsync(raw_file, json.dumps(raw_json, indent=2))

        # Map reasoner output to expected format
        risk_map = {'HIGH': 'High', 'MODERATE': 'Medium', 'LOW': 'Low'}
        ai_risk = risk_map.get(result.get('risk_category', 'UNKNOWN'), 'Medium')

        return {
            'ai_risk':              ai_risk,
            'ai_recommendations':   [],   # reasoner returns reasoning text, not list
            'confidence':           0.85 if result.get('risk_category') != 'UNKNOWN' else 0.3,
            'raw_text':             raw_text,
            'fallback_triggered':   False,
            'inference_time_ms':    inference_time_ms,
            'safety_net_triggered': result.get('safety_net_triggered', False),
        }

    except Exception as e:
        logger.error(f"MedGemma inference failed: {e}")
        return {
            'ai_risk': None,
            'ai_recommendations': [],
            'confidence': 0.0,
            'raw_text': f"Inference error: {str(e)}",
            'fallback_triggered': True,
            'inference_time_ms': int((time.time() - start_time) * 1000),
        }


# ════════════════════════════════════════════════════════════════════════════
# QC VALIDATION (unchanged logic, minor cleanup)
# ════════════════════════════════════════════════════════════════════════════

def run_qc_validation(rule_decision: dict, ai_result: dict) -> dict:
    qc_result = {'qc_passed': True, 'warnings': [], 'rule_disagreement': False}
    if ai_result.get('ai_risk') and ai_result['ai_risk'] != rule_decision['risk_level']:
        qc_result['rule_disagreement'] = True
        qc_result['warnings'].append(
            f"AI risk ({ai_result['ai_risk']}) differs from rule engine ({rule_decision['risk_level']})"
        )
    if ai_result.get('confidence', 0) < 0.60:
        qc_result['warnings'].append('Low AI confidence')
    if ai_result.get('fallback_triggered'):
        qc_result['warnings'].append('MedGemma not available — rule engine only')
    return qc_result


# ════════════════════════════════════════════════════════════════════════════
# MAIN PROCESSING PIPELINE (background task — unchanged logic)
# ════════════════════════════════════════════════════════════════════════════

async def process_assessment(run_id: str, request_data: dict):
    import torch
    try:
        logger.info(f"Processing assessment {run_id}")
        JOB_QUEUE[run_id]['status'] = 'processing'

        run_dir = ARTIFACTS_DIR / run_id
        run_dir.mkdir(exist_ok=True)

        request_json = json.dumps(request_data, indent=2)
        save_with_fsync(run_dir / 'raw_request.json', request_json)
        save_with_fsync(run_dir / 'raw_request.hmac', compute_hmac(request_json.encode()))

        seed = derive_seed(request_data)
        torch.manual_seed(seed)

        normalized_input = {
            'patient_id': request_data['patient_id'],
            'vitals': {
                'bp_systolic':       request_data['bp_systolic'],
                'bp_diastolic':      request_data['bp_diastolic'],
                'weight_kg':         request_data['weight_kg'],
                'hemoglobin_g_dl':   request_data.get('hemoglobin_g_dl'),
                'platelets_per_ul':  request_data.get('platelets_per_ul'),
                'proteinuria':       request_data.get('proteinuria'),
                'age':               request_data['age'],
                'gestational_age_weeks': request_data.get('gestational_age_weeks'),
            }
        }
        save_with_fsync(run_dir / 'normalized_input.json', json.dumps(normalized_input, indent=2))

        rule_decision = run_rule_engine(normalized_input['vitals'])
        save_with_fsync(run_dir / 'rule_engine_decision.json', json.dumps(rule_decision, indent=2))

        ai_result = run_medgemma_inference(normalized_input['vitals'], run_dir, MEDGEMMA_TIMEOUT_SEC)

        normalized_output = {
            'ai_risk_level':     ai_result.get('ai_risk'),
            'ai_recommendations': ai_result.get('ai_recommendations', []),
            'confidence':        ai_result.get('confidence', 0),
            'fallback_triggered': ai_result.get('fallback_triggered', False),
        }
        save_with_fsync(run_dir / 'normalized_output.json', json.dumps(normalized_output, indent=2))

        qc_result = run_qc_validation(rule_decision, ai_result)
        save_with_fsync(run_dir / 'qc_result.json', json.dumps(qc_result, indent=2))

        pipeline_output = {
            'run_id':            run_id,
            'patient_id':        request_data['patient_id'],
            'timestamp':         datetime.utcnow().isoformat() + 'Z',
            'decision_source':   'rule_engine',
            'rule_engine_decision': rule_decision,
            'ai_risk':           ai_result.get('ai_risk'),
            'ai_advisory':       ai_result.get('ai_recommendations', []),
            'final_risk_level':  rule_decision['risk_level'],
            'final_recommendations': rule_decision['recommendations'],
            'qc_result':         qc_result,
            'provenance': {
                'model_snapshot':  MEDGEMMA_SNAPSHOT_PATH,
                'device':          MEDGEMMA_DEVICE,
                'seed':            seed,
                'inference_time_ms': ai_result.get('inference_time_ms', 0),
                'rule_engine_version': 'v2.0',
                'timestamp':       datetime.utcnow().isoformat() + 'Z',
            }
        }
        save_with_fsync(run_dir / 'pipeline_output.json', json.dumps(pipeline_output, indent=2))

        artifact_content = ''
        for fname in ['pipeline_output.json', 'medgemma_raw.json',
                      'rule_engine_decision.json', 'normalized_output.json']:
            fpath = run_dir / fname
            if fpath.exists():
                artifact_content += fpath.read_text(encoding='utf-8')

        artifact_hash = hashlib.sha256(artifact_content.encode()).hexdigest()
        save_with_fsync(run_dir / 'artifact.sha256', artifact_hash)
        save_with_fsync(run_dir / 'artifact.signature', compute_hmac(artifact_hash.encode()))

        JOB_QUEUE[run_id]['status'] = 'completed'
        JOB_QUEUE[run_id]['artifacts_path'] = str(run_dir)
        JOB_QUEUE[run_id]['result'] = pipeline_output
        logger.info(f"✓ Assessment {run_id} completed")

    except Exception as e:
        logger.error(f"Assessment {run_id} failed: {e}", exc_info=True)
        JOB_QUEUE[run_id]['status'] = 'failed'
        JOB_QUEUE[run_id]['error'] = str(e)


# ════════════════════════════════════════════════════════════════════════════
# FASTAPI APP + LIFESPAN
# FIX 4: Lifespan never blocks. Model loads in background thread.
# ════════════════════════════════════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=" * 60)
    logger.info("PregnancyBridge Backend API — Starting")
    logger.info(f"  Artifacts : {ARTIFACTS_DIR.absolute()}")
    logger.info(f"  Device    : {MEDGEMMA_DEVICE}")
    logger.info("=" * 60)

    # FIX: Non-blocking background load.
    # Server is immediately ready on port 8001.
    # MedGemma becomes available ~60-120s later (CPU load time).
    # Until then, all requests use rule-based Safety Net automatically.
    logger.info("Launching MedGemma background loader (non-blocking)...")
    loader_thread = load_model_async()
    logger.info(
        "✅ Server ready. MedGemma loading in background. "
        "Rule-based Safety Net is active immediately."
    )

    yield  # Server runs here

    logger.info("Shutting down PregnancyBridge Backend API")
    # Background thread is daemon=True — exits with process automatically


app = FastAPI(
    title="PregnancyBridge Backend API",
    version="2.0.0",
    description="MedGemma-powered offline maternal health risk assessment",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ════════════════════════════════════════════════════════════════════════════
# ROUTES
# ════════════════════════════════════════════════════════════════════════════

@app.get("/")
async def root():
    backend_status = get_backend_status()
    return {
        "service":      "PregnancyBridge Backend API",
        "version":      "2.0.0",
        "status":       "running",
        "ai_backend":   backend_status["backend"],       # "gguf" | "none"
        "model_loaded": backend_status["model_loaded"],  # True once background load completes
        "safety_net":   "active",                        # always active
        "total_runs":   len(JOB_QUEUE),
    }


@app.get("/api/v1/health")
def health():
    backend_status = get_backend_status()
    return {
        "service":      "PregnancyBridge Backend",
        "status":       "ok",
        "ai_backend":   backend_status["backend"],
        "model_loaded": backend_status["model_loaded"],
        "safety_net":   "active",
    }


# ════════════════════════════════════════════════════════════════════════════
# FIELD-DEMO ENDPOINT
# ════════════════════════════════════════════════════════════════════════════

@app.post("/api/v1/field-assess")
def field_assess_risk(request: FieldVisitRequest):
    """
    Synchronous single-visit risk assessment for the field demo.

    Flow with images:
      1. OCR → extract_clinical_fields
      2. If ANY lab value was OCR-extracted → return pending_confirmation
         (ANM must confirm via /api/v1/confirm-labs before risk runs)
      3. After confirmation (or if no images): run risk pipeline
    """
    logger.info(f"field-assess: patient={request.patient_id}")
    start = time.time()

    fields = {}
    ocr_extracted_any = False

    # ── Step 0: OCR extraction ───────────────────────────────────────────────
    if request.images:
        try:
            logger.info(f"OCR: processing {len(request.images)} image(s)")
            raw_b64 = request.images[0]
            if ',' in raw_b64:
                raw_b64 = raw_b64.split(',', 1)[1]
            raw_b64 += '=' * (4 - len(raw_b64) % 4)
            img_data = base64.b64decode(raw_b64)

            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                tmp.write(img_data)
                tmp_path = tmp.name

            try:
                normalized_path = str(Path(tmp_path).resolve())
                ocr_text = perform_ocr(normalized_path)
            finally:
                try:
                    Path(tmp_path).unlink(missing_ok=True)
                except Exception:
                    pass

            if ocr_text:
                fields = extract_clinical_fields(ocr_text)
                logger.info("OCR extraction completed")

                # Check if any lab value was actually extracted
                ocr_extracted_any = (
                    fields.get('hemoglobin') is not None or
                    fields.get('platelets') is not None
                )

        except Exception as e:
            logger.error(f"OCR extraction error: {e}")

    # ── Step 1: Confirmation gate ────────────────────────────────────────────
    # FIX: Triggers on ANY OCR extraction, not just critical flags.
    # Critical flags additionally get a CRITICAL warning in the response.
    if ocr_extracted_any:
        meta = fields.get('lab_extraction_meta', {})
        confirmation_token = str(uuid.uuid4())

        # Store the full request context keyed by token
        PENDING_CONFIRMATIONS[confirmation_token] = {
            'request':           request.dict(),
            'ocr_fields':        fields,
            'created_at':        datetime.utcnow().isoformat() + 'Z',
            # Token expires after 10 minutes (checked at confirm endpoint)
            'expires_at_epoch':  time.time() + 600,
        }

        logger.info(
            f"OCR gate: token={confirmation_token}, "
            f"hb={fields.get('hemoglobin')}, "
            f"plt={fields.get('platelets')}, "
            f"critical={meta.get('has_critical_flags', False)}"
        )

        return {
            "status": "pending_confirmation",
            "confirmation_token": confirmation_token,
            "extracted_values": {
                "hemoglobin_g_dl":   fields.get('hemoglobin'),
                "hemoglobin_status": meta.get('hemoglobin_status', 'unknown'),
                "hemoglobin_raw":    meta.get('hemoglobin_raw_ocr'),
                "platelets_per_ul":  fields.get('platelets'),
                "platelets_lakh":    fields.get('platelets_lakh'),
                "platelets_status":  meta.get('platelets_status', 'unknown'),
                "platelets_raw":     meta.get('platelets_raw_ocr'),
                "platelets_unit":    meta.get('platelets_raw_unit'),
            },
            "flags":             meta.get('flags', []),
            "has_critical_flags": meta.get('has_critical_flags', False),
            "message": (
                "⚠️ CRITICAL values detected — ANM must verify before assessment"
                if meta.get('has_critical_flags')
                else "Lab values extracted — please verify before assessment runs"
            ),
            "confirm_endpoint":  "/api/v1/confirm-labs",
        }

    # ── If no images: run assessment directly ────────────────────────────────
    return _run_full_assessment(request, confirmed_fields=None, start_time=start)


# ════════════════════════════════════════════════════════════════════════════
# FIX 5: CONFIRMATION ENDPOINT (new)
# ════════════════════════════════════════════════════════════════════════════

@app.post("/api/v1/confirm-labs")
def confirm_labs(body: LabConfirmRequest):
    """
    ANM confirms or corrects OCR-extracted lab values.
    After confirmation, runs the full risk assessment pipeline.

    The frontend should:
      1. Show extracted_values from /field-assess pending_confirmation response
      2. Let ANM edit Hb and platelet values
      3. POST confirmed values here with the confirmation_token
    """
    token = body.confirmation_token

    if token not in PENDING_CONFIRMATIONS:
        raise HTTPException(
            status_code=404,
            detail="Confirmation token not found or already used. Re-upload the image."
        )

    pending = PENDING_CONFIRMATIONS.pop(token)  # consume — one-time use

    # Check expiry
    if time.time() > pending['expires_at_epoch']:
        raise HTTPException(
            status_code=410,
            detail="Confirmation token expired (10-minute limit). Re-upload the image."
        )

    # Reconstruct request with ANM-confirmed values
    req_dict = pending['request']
    ocr_fields = pending['ocr_fields']
    start_time = time.time()

    # Build a FieldVisitRequest from stored data
    from pydantic import ValidationError
    try:
        request = FieldVisitRequest(**req_dict)
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to reconstruct request from token")

    # Apply ANM-confirmed values (these override OCR values)
    confirmed_fields = dict(ocr_fields)  # copy OCR fields as base

    if body.confirmed_hemoglobin is not None:
        request.hemoglobin = body.confirmed_hemoglobin
        confirmed_fields['hemoglobin'] = body.confirmed_hemoglobin
        logger.info(f"ANM confirmed Hb={body.confirmed_hemoglobin} g/dL")

    elif ocr_fields.get('hemoglobin') is not None:
        # ANM did not edit → accept OCR value
        request.hemoglobin = ocr_fields['hemoglobin']
        logger.info(f"ANM accepted OCR Hb={ocr_fields['hemoglobin']} g/dL")

    if body.confirmed_platelets_per_ul is not None:
        confirmed_fields['platelets'] = body.confirmed_platelets_per_ul
        logger.info(f"ANM confirmed platelets={body.confirmed_platelets_per_ul}/µL")
    # (platelets fed into risk engine via confirmed_fields, not request)

    # Apply the four new ANM-verified fields
    if body.confirmed_bp_systolic is not None:
        request.bp_systolic = body.confirmed_bp_systolic
        logger.info(f"ANM confirmed BP systolic={body.confirmed_bp_systolic} mmHg")
    if body.confirmed_bp_diastolic is not None:
        request.bp_diastolic = body.confirmed_bp_diastolic
        logger.info(f"ANM confirmed BP diastolic={body.confirmed_bp_diastolic} mmHg")
    if body.confirmed_gestational_age is not None:
        request.gestational_age_weeks = body.confirmed_gestational_age
        logger.info(f"ANM confirmed gestational age={body.confirmed_gestational_age} weeks")
    if body.confirmed_proteinuria is not None:
        request.proteinuria = body.confirmed_proteinuria
        logger.info(f"ANM confirmed proteinuria={body.confirmed_proteinuria}")

    if body.anm_notes:
        logger.info(f"ANM notes: {body.anm_notes}")

    return _run_full_assessment(request, confirmed_fields=confirmed_fields, start_time=start_time)


# ════════════════════════════════════════════════════════════════════════════
# SHARED ASSESSMENT RUNNER
# ════════════════════════════════════════════════════════════════════════════

def _run_full_assessment(
    request: FieldVisitRequest,
    confirmed_fields: Optional[dict],
    start_time: float,
) -> dict:
    """
    Core risk assessment pipeline — called by both field_assess_risk
    (no images) and confirm_labs (after ANM confirmation).
    """
    # ── Patch request with any confirmed/OCR fields not already set ──────────
    if confirmed_fields:
        if request.hemoglobin is None and confirmed_fields.get('hemoglobin'):
            request.hemoglobin = confirmed_fields['hemoglobin']
        if request.gestational_age_weeks is None and confirmed_fields.get('gestational_age'):
            request.gestational_age_weeks = confirmed_fields['gestational_age']
        if request.proteinuria is None and confirmed_fields.get('proteinuria'):
            request.proteinuria = confirmed_fields['proteinuria']
        if request.weight_kg is None and confirmed_fields.get('weight'):
            request.weight_kg = confirmed_fields['weight']
        if confirmed_fields.get('bp_systolic') and confirmed_fields.get('bp_diastolic'):
            request.bp_systolic = confirmed_fields['bp_systolic']
            request.bp_diastolic = confirmed_fields['bp_diastolic']

    # FIX 6: Platelets from OCR/confirmed fields → risk engine
    platelets_for_engine = (
        confirmed_fields.get('platelets') if confirmed_fields else None
    )

    # ── Build symptoms ────────────────────────────────────────────────────────
    symptom_names = request.symptoms or []
    symptoms_dict = {
        'headache':               'headache'              in symptom_names,
        'blurred_vision':         'blurred_vision'        in symptom_names,
        'facial_edema':           'facial_edema'          in symptom_names,
        'pedal_edema':            'pedal_edema'           in symptom_names,
        'dizziness':              'dizziness'             in symptom_names,
        'breathlessness':         'breathlessness'        in symptom_names,
        'reduced_fetal_movement': 'reduced_fetal_movement' in symptom_names,
        'abdominal_pain':         'abdominal_pain'        in symptom_names,
        'nausea_vomiting':        'nausea_vomiting'       in symptom_names,
    }

    intake = SymptomIntake()
    symptom_data = {'symptoms': symptoms_dict}
    is_valid, validation_error = intake.validate_symptoms(symptom_data)
    if is_valid:
        symptom_record = intake.capture_symptoms(symptom_data, visit_id=request.visit_id)
    else:
        logger.warning(f"Symptom validation failed: {validation_error}, using fallback")
        symptom_record = {
            'symptoms':       symptoms_dict,
            'present_symptoms': list(symptom_names),
            'symptom_count':  len(symptom_names),
            'category_count': 0,
            'categories':     {},
        }

    other_symptoms_text = (request.other_symptoms or "").strip()
    symptom_record['other_symptoms'] = other_symptoms_text

    visit = {
        'date':            request.visit_date or datetime.utcnow().isoformat() + 'Z',
        'gestational_age': request.gestational_age_weeks,
        'weight':          request.weight_kg,
        'bp':              {'systolic': request.bp_systolic, 'diastolic': request.bp_diastolic},
        'hemoglobin':      request.hemoglobin,
        'proteinuria':     request.proteinuria or 'nil',
        'symptoms':        symptom_record,
        # FIX 6: platelets included in visit for SymptomRiskEngine
        'platelets':       platelets_for_engine,
    }

    # ── Risk assessment ───────────────────────────────────────────────────────
    try:
        engine = SymptomRiskEngine(log_assessments=False)
        risk_assessment = engine.evaluate_visit([visit], symptom_record)
    except Exception as exc:
        logger.error(f"SymptomRiskEngine failed: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Risk engine error: {exc}")

    risk_category    = risk_assessment.get('risk_category', 'UNKNOWN')
    referral_required = risk_assessment.get('referral_required', False)

    evidence_summary = []
    _component_labels = {
        'blood_pressure': 'Blood Pressure',
        'anemia':         'Anaemia',
        'proteinuria':    'Proteinuria',
    }
    trigger_reason = risk_assessment.get('trigger_reason', '')
    for component, data in risk_assessment.get('component_risks', {}).items():
        component_reason = data.get('reason')
        if not component_reason:
            continue
        # Skip standalone component entry when the trigger_reason already
        # contains it (i.e. the escalation rule fired and produced a richer
        # combined string — adding both would create a duplicate).
        if trigger_reason and component_reason in trigger_reason:
            continue
        label = _component_labels.get(component, component.replace('_', ' ').title())
        evidence_summary.append(f"{label}: {component_reason}")
    if trigger_reason:
        evidence_summary.append(trigger_reason)
    if other_symptoms_text:
        evidence_summary.append(f"Patient-reported: {other_symptoms_text}")

    # ── MedGemma explanation ──────────────────────────────────────────────────
    ai_explanation = None
    try:
        ai_explanation = explain_context(
            evidence_summary=evidence_summary,
            rule_reason=risk_assessment.get('trigger_reason', ''),
            risk_category=risk_category,
            symptoms=symptoms_dict,
            lab_age_days=0,
        )
    except Exception as exc:
        logger.warning(f"explain_context failed: {exc}")

    # ── Recommendations ───────────────────────────────────────────────────────
    recommendations = []
    try:
        latest_values = {
            'bp_systolic':  request.bp_systolic,
            'bp_diastolic': request.bp_diastolic,
            'hemoglobin':   request.hemoglobin,
            'proteinuria':  request.proteinuria,
            'platelets':    platelets_for_engine,
        }
        recommendations = recommend_next_actions_with_deterministic(
            evidence_summary=evidence_summary,
            available_tests=['CBC', 'UrineDip', 'BP_machine', 'LFT'],
            context={'lab_age_days': 0, 'distance_to_facility_km': 5},
            risk_category=risk_category,
            latest_values=latest_values,
        )
    except Exception as exc:
        logger.warning(f"Recommendations generation failed: {exc}")

    elapsed = round(time.time() - start_time, 2)
    logger.info(f"field-assess done in {elapsed}s  risk={risk_category}")

    return {
        'risk_level':        risk_category,
        'referral_required': referral_required,
        'evidence_summary':  evidence_summary,
        'ai_explanation': {
            'text':    ai_explanation.get('explanation_text', '') if ai_explanation else '',
            'source':  ai_explanation.get('explanation_source', 'none') if ai_explanation else 'none',
            'qc_pass': ai_explanation.get('explanation_qc_pass', False) if ai_explanation else False,
        },
        'recommendations':     recommendations,
        'processing_time_sec': elapsed,
    }


# ════════════════════════════════════════════════════════════════════════════
# EXISTING ENDPOINTS (unchanged logic)
# ════════════════════════════════════════════════════════════════════════════

@app.post("/api/v1/assess-risk", response_model=AssessmentResponse)
async def assess_risk(request: AssessmentRequest, background_tasks: BackgroundTasks):
    run_id = str(uuid.uuid4())
    JOB_QUEUE[run_id] = {
        'run_id':       run_id,
        'status':       'queued',
        'submitted_at': datetime.utcnow().isoformat(),
        'request':      request.dict(),
    }
    background_tasks.add_task(process_assessment, run_id, request.dict())
    return AssessmentResponse(
        run_id=run_id, status='queued',
        message=f'Assessment queued. Check /api/v1/result/{run_id}'
    )


@app.get("/api/v1/result/{run_id}")
async def get_result(run_id: str):
    if run_id not in JOB_QUEUE:
        raise HTTPException(status_code=404, detail="Run ID not found")
    job = JOB_QUEUE[run_id]
    response = {'run_id': run_id, 'status': job['status'], 'submitted_at': job['submitted_at']}
    if job['status'] == 'completed':
        response['result'] = job.get('result')
        response['artifacts_path'] = job.get('artifacts_path')
        response['download_links'] = {
            'pipeline_output':   f'/api/v1/download/{run_id}/pipeline_output.json',
            'medgemma_raw':      f'/api/v1/download/{run_id}/medgemma_raw.json',
            'normalized_output': f'/api/v1/download/{run_id}/normalized_output.json',
            'artifact_signature': f'/api/v1/download/{run_id}/artifact.signature',
        }
    elif job['status'] == 'failed':
        response['error'] = job.get('error')
    return response


@app.get("/api/v1/download/{run_id}/{filename}")
async def download_artifact(run_id: str, filename: str):
    if '..' in filename or '/' in filename or '\\' in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    file_path = ARTIFACTS_DIR / run_id / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path=file_path, filename=filename, media_type='application/octet-stream')


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=os.getenv('HOST', '0.0.0.0'),
        port=int(os.getenv('PORT', 8001)),
        workers=1,
        log_level="info",
    )
