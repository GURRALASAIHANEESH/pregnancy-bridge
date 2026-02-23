"""
medgemma_extractor.py — PregnancyBridge Clinical Reasoning Engine
=================================================================

ARCHITECTURE CHANGE from original:
  Original: init_empty_weights → infer_auto_device_map → load_checkpoint_and_dispatch
  Problem:  Materializes ALL CPU-mapped modules simultaneously before dispatch.
            Needs ~6-7GB free RAM. Kills process at layer 14 on 4.8GB free RAM.
            No Python exception — Windows OOM-kills the process silently.

  New: Two-tier loader:
    Tier 1 — llama-cpp-python + GGUF (preferred, ~2.5GB RAM, mmap streaming)
    Tier 2 — transformers from_pretrained with strict CPU memory cap (fallback)
    Tier 3 — model=None → Safety Net handles all requests (always available)

  Loading is ALWAYS non-blocking:
    - __init__() sets self.model = None and returns immediately
    - load_model() is called only from load_model_async() (background thread)
    - get_clinical_reasoner() returns singleton without triggering any load
    - app.py calls load_model_async() once at startup

GGUF SETUP (one-time, run before starting server):
  pip install llama-cpp-python --extra-index-url \
      https://abetlen.github.io/llama-cpp-python/whl/cpu

  Download the GGUF model (~2.5GB) to D:\\huggingface_cache:
  python -c "
  from huggingface_hub import hf_hub_download
  hf_hub_download(
      repo_id='bartowski/medgemma-1.5-4b-it-GGUF',
      filename='medgemma-1.5-4b-it-Q4_K_M.gguf',
      local_dir=r'D:/huggingface_cache'
  )
  "
"""

import gc
import logging
import os
import threading
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────
HF_CACHE_DIR   = Path(r"D:\huggingface_cache")
GGUF_PATH = HF_CACHE_DIR / "medgemma-1.5-4b-it.Q4_K_M.gguf"
OFFLOAD_DIR    = Path(r"D:\medgemma_offload")

# HF snapshot path (for Tier 2 fallback — uses existing download)
HF_SNAPSHOT_BASE = HF_CACHE_DIR / "hub" / "models--google--medgemma-1.5-4b-it"

# llama-cpp settings
N_CTX     = 4096                          # context window — 4096 gives room for output (prompt ~1900 tok)
N_THREADS = max(4, (os.cpu_count() or 4)) # use all physical cores

# Tier 2 memory cap — deliberately conservative
TIER2_MAX_MEMORY_GB = "3GiB"


# ── Singleton state ────────────────────────────────────────────────────────────
_instance: Optional["MedGemmaClinicalReasoner"] = None
_instance_lock = threading.Lock()


# ════════════════════════════════════════════════════════════════════════════
# PUBLIC API — these are what app.py imports
# ════════════════════════════════════════════════════════════════════════════

def get_clinical_reasoner(force_cpu: bool = True) -> "MedGemmaClinicalReasoner":
    """
    Return the singleton MedGemmaClinicalReasoner.
    NEVER triggers a model load — just returns the instance.
    Instance.model may be None if background load hasn't completed yet.
    Callers must check: if reasoner.model is None → use Safety Net.
    """
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = MedGemmaClinicalReasoner()
    return _instance


def load_model_async() -> threading.Thread:
    """
    Launch background thread to load the model.
    Call once from FastAPI lifespan — returns immediately.
    Server is available on port 8001 before model finishes loading.
    """
    reasoner = get_clinical_reasoner()
    t = threading.Thread(
        target=reasoner.load_model,
        daemon=True,
        name="medgemma-loader"
    )
    t.start()
    logger.info("MedGemma background loader started (thread: medgemma-loader)")
    return t


def get_backend_status() -> dict:
    """Return current loader state — used by /health and / endpoints."""
    reasoner = get_clinical_reasoner()
    return {
        "backend":          reasoner.backend,
        "model_loaded":     reasoner.model is not None,
        "load_attempted":   reasoner.load_attempted,
        "gguf_file_exists": GGUF_PATH.exists(),
        "gguf_path":        str(GGUF_PATH),
        "error":            reasoner.last_error,
    }


# ════════════════════════════════════════════════════════════════════════════
# REASONER CLASS
# ════════════════════════════════════════════════════════════════════════════

class MedGemmaClinicalReasoner:
    """
    MedGemma clinical reasoning engine with two-tier loader.
    
    State machine:
      backend = "unloaded" → load_model() called → "loading"
                           → success → "gguf" or "transformers"
                           → failure → "none" (Safety Net takes over)
    """

    def __init__(self):
        # All state initialized to safe defaults — NO model load here
        self.model         = None   # llama_cpp.Llama OR transformers model OR None
        self.tokenizer     = None   # only set in Tier 2 path
        self.backend       = "unloaded"   # "gguf" | "transformers" | "none" | "unloaded"
        self.load_attempted = False
        self.last_error    = None
        self.model_snapshot = None
        self._load_lock    = threading.Lock()

    # ── Public: non-blocking loader entry point ───────────────────────────────

    def load_model(self) -> bool:
        """
        Attempt model load. NEVER raises — all exceptions caught.
        Returns True on success, False on any failure.
        Sets self.model, self.backend, self.last_error.
        Thread-safe: subsequent calls are no-ops if already attempted.
        """
        with self._load_lock:
            if self.load_attempted:
                return self.model is not None
            self.load_attempted = True
            self.backend = "loading"

        logger.info("=" * 55)
        logger.info("MedGemma loader starting")
        logger.info(f"  GGUF path : {GGUF_PATH}")
        logger.info(f"  GGUF exists: {GGUF_PATH.exists()}")
        logger.info(f"  n_ctx     : {N_CTX}")
        logger.info(f"  n_threads : {N_THREADS}")
        logger.info("=" * 55)

        # Try Tier 1 first, then Tier 2
        success = self._load_tier1_gguf()
        if not success:
            logger.warning("Tier 1 (GGUF) failed — attempting Tier 2 (transformers)")
            success = self._load_tier2_transformers()

        if not success:
            self.backend = "none"
            logger.error(
                "Both tiers failed. Server running in Safety Net-only mode. "
                "All clinical decisions made by deterministic rule engine."
            )

        gc.collect()
        return success

    # ── Tier 1: llama-cpp-python + GGUF ──────────────────────────────────────

    def _load_tier1_gguf(self) -> bool:
        """
        Load via llama-cpp-python (CPU, mmap, ~2.5GB peak RAM).
        
        Why this works where load_checkpoint_and_dispatch fails:
          - mmap: weights are read from disk per-token, not loaded into RAM upfront
          - Peak RAM = model file size (~2.5GB Q4_K_M), not full precision (~8GB)
          - No dispatch hooks, no materialization step
        """
        if not GGUF_PATH.exists():
            logger.warning(
                f"[Tier1] GGUF not found at {GGUF_PATH}\n"
                "  Run this once to download (~2.5GB):\n"
                "  python -c \"\n"
                "  from huggingface_hub import hf_hub_download\n"
                "  hf_hub_download(\n"
                "      repo_id='bartowski/medgemma-1.5-4b-it-GGUF',\n"
                "      filename='medgemma-1.5-4b-it-Q4_K_M.gguf',\n"
                "      local_dir=r'D:/huggingface_cache'\n"
                "  )\""
            )
            return False

        try:
            from llama_cpp import Llama  # type: ignore
        except ImportError:
            logger.warning(
                "[Tier1] llama-cpp-python not installed.\n"
                "  Run: pip install llama-cpp-python --extra-index-url "
                "https://abetlen.github.io/llama-cpp-python/whl/cpu"
            )
            return False

        try:
            logger.info(f"[Tier1] Loading GGUF: {GGUF_PATH.name} ...")
            t0 = time.time()

            llm = Llama(
                model_path   = str(GGUF_PATH),
                n_ctx        = N_CTX,
                n_threads    = N_THREADS,
                n_gpu_layers = 0,       # CPU only — no GPU on this machine
                use_mmap     = True,    # mmap from disk → lower RAM spike
                use_mlock    = False,   # don't pin pages — let OS manage pressure
                verbose      = False,
            )

            elapsed = time.time() - t0
            self.model          = llm
            self.backend        = "gguf"
            self.model_snapshot = str(GGUF_PATH)
            logger.info(f"[Tier1] ✅ GGUF loaded in {elapsed:.1f}s")
            return True

        except MemoryError:
            logger.error("[Tier1] OOM during GGUF load — not enough free RAM even for GGUF")
            self.last_error = "OOM: GGUF load failed"
            return False
        except Exception as e:
            logger.error(f"[Tier1] Unexpected error: {type(e).__name__}: {e}")
            self.last_error = str(e)
            return False

    # ── Tier 2: transformers from_pretrained (last resort) ───────────────────

    def _load_tier2_transformers(self) -> bool:
        """
        Last-resort: load from HF safetensors with strict CPU memory cap.
        
        Uses from_pretrained with:
          - torch_dtype=bfloat16 (halves model size vs float32)
          - device_map="cpu" (no disk offload — avoids dispatch materialization)
          - max_memory strictly capped
          
        This avoids load_checkpoint_and_dispatch entirely.
        If this also OOMs, we fall through to Safety Net.
        """
        # Locate snapshot directory
        snapshot_dir = self._find_snapshot_dir()
        if snapshot_dir is None:
            logger.warning(
                f"[Tier2] No HF snapshot found under {HF_SNAPSHOT_BASE}. "
                "Skipping Tier 2."
            )
            return False

        try:
            import torch
            from transformers import AutoConfig, AutoModelForCausalLM, AutoTokenizer
        except ImportError as e:
            logger.error(f"[Tier2] transformers/torch not available: {e}")
            return False

        try:
            logger.info(f"[Tier2] Loading from HF snapshot: {snapshot_dir}")
            logger.info(f"[Tier2] Memory cap: {TIER2_MAX_MEMORY_GB}, dtype: bfloat16")
            t0 = time.time()

            # Tokenizer first (tiny, just JSON files)
            try:
                from transformers import GemmaTokenizer
                tokenizer = GemmaTokenizer.from_pretrained(
                    str(snapshot_dir),
                    local_files_only=True,
                    trust_remote_code=True,
                )
            except Exception:
                tokenizer = AutoTokenizer.from_pretrained(
                    str(snapshot_dir),
                    local_files_only=True,
                    trust_remote_code=True,
                    use_fast=False,
                )

            if tokenizer.pad_token is None:
                tokenizer.pad_token = tokenizer.eos_token

            # Force gc before heavy load
            gc.collect()

            # Load with from_pretrained — NO accelerate dispatch
            # device_map="cpu" with max_memory cap avoids the materialization bug
            model = AutoModelForCausalLM.from_pretrained(
                str(snapshot_dir),
                torch_dtype        = torch.bfloat16,
                device_map         = "cpu",
                max_memory         = {"cpu": TIER2_MAX_MEMORY_GB},
                local_files_only   = True,
                trust_remote_code  = True,
                low_cpu_mem_usage  = True,
            )
            model.eval()
            gc.collect()

            elapsed = time.time() - t0
            self.model          = model
            self.tokenizer      = tokenizer
            self.backend        = "transformers"
            self.model_snapshot = str(snapshot_dir)
            logger.info(f"[Tier2] ✅ transformers model loaded in {elapsed:.1f}s")
            return True

        except MemoryError:
            logger.error(
                f"[Tier2] OOM during transformers load. "
                f"System has less than {TIER2_MAX_MEMORY_GB} free. "
                "Falling back to Safety Net."
            )
            self.last_error = "OOM: transformers load failed"
            self.model = None
            gc.collect()
            return False
        except Exception as e:
            logger.error(f"[Tier2] Failed: {type(e).__name__}: {e}")
            self.last_error = str(e)
            self.model = None
            gc.collect()
            return False

    def _find_snapshot_dir(self) -> Optional[Path]:
        """Find the latest HF snapshot directory for medgemma."""
        if not HF_SNAPSHOT_BASE.exists():
            return None
        snapshots = sorted((HF_SNAPSHOT_BASE / "snapshots").glob("*"))
        return snapshots[-1] if snapshots else None

    # ── Inference ─────────────────────────────────────────────────────────────

    def reason_about_case(self, structured_data: dict) -> dict:
        """
        Run clinical reasoning. Returns structured result dict.
        NEVER raises — returns error dict on any failure.
        Caller in app.py must check: if model is None → skip this, use Safety Net.
        """
        if self.model is None:
            return {
                "risk_category":      "UNKNOWN",
                "reasoning":          "MedGemma not loaded — Safety Net is authoritative",
                "confidence":         "low",
                "referral_urgent":    False,
                "hardware_used":      "none",
                "inference_time_ms":  0,
                "safety_net_triggered": False,
                "fallback":           True,
            }

        start = time.time()

        try:
            if structured_data.get("prompt_override"):
                prompt = structured_data["prompt_override"]
            else:
                prompt = self._build_clinical_prompt(structured_data)

            if self.backend == "gguf":
                return self._infer_gguf(prompt, structured_data, start)
            else:
                return self._infer_transformers(prompt, structured_data, start)

        except Exception as e:
            inference_time_ms = (time.time() - start) * 1000
            logger.error(f"Inference failed: {type(e).__name__}: {e}")
            return {
                "risk_category":      "UNKNOWN",
                "reasoning":          f"Inference error: {str(e)}",
                "confidence":         "low",
                "referral_urgent":    False,
                "hardware_used":      "CPU",
                "inference_time_ms":  round(inference_time_ms, 1),
                "error":              str(e),
                "fallback":           True,
            }

    # ── GGUF inference path ───────────────────────────────────────────────────

    def _infer_gguf(self, prompt: str, original_data: dict, start: float) -> dict:
        response = self.model(
            prompt,
            max_tokens  = 256,          # enough for ~3 clinical sentences
            temperature = 0.0,          # greedy — deterministic for clinical use
            stop        = [
                "</s>",
                "\n\n\n",              # hard stop on 3+ blank lines (clear end-of-output)
                "Question:",           # stops if model hallucinates a Q&A loop
                "Patient:",            # stops if model starts a new case header
                "**Your response",     # stops on markdown-bold prompt leakage
                "Your response:",      # stops on plain-text prompt leakage
            ],
            echo        = False,
        )
        raw_text = response["choices"][0]["text"].strip()
        inference_time_ms = (time.time() - start) * 1000

        logger.info(f"[GGUF] Inference: {inference_time_ms:.0f}ms | {len(raw_text)} chars")
        logger.info(f"[GGUF] Preview: {raw_text[:120]}")

        result = self._parse_reasoning_output(raw_text, original_data)
        result["hardware_used"]      = "CPU (GGUF)"
        result["inference_time_ms"]  = round(inference_time_ms, 1)
        result["model_snapshot"]     = self.model_snapshot
        return result

    # ── Transformers inference path ───────────────────────────────────────────

    def _infer_transformers(self, prompt: str, original_data: dict, start: float) -> dict:
        import torch

        inputs = self.tokenizer(
            prompt,
            return_tensors = "pt",
            truncation     = True,
            max_length     = 1024,
        )
        inputs = {k: v.to("cpu") for k, v in inputs.items()}

        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens  = 120,
                do_sample       = False,
                temperature     = None,
                pad_token_id    = self.tokenizer.pad_token_id,
                eos_token_id    = self.tokenizer.eos_token_id,
            )

        raw_text = self.tokenizer.decode(
            outputs[0][inputs["input_ids"].shape[1]:],
            skip_special_tokens=True,
        )
        inference_time_ms = (time.time() - start) * 1000

        logger.info(f"[Transformers] Inference: {inference_time_ms:.0f}ms")

        result = self._parse_reasoning_output(raw_text, original_data)
        result["hardware_used"]     = "CPU (transformers)"
        result["inference_time_ms"] = round(inference_time_ms, 1)
        result["model_snapshot"]    = self.model_snapshot
        return result

    # ── Prompt builder (unchanged from original) ──────────────────────────────

    def _build_clinical_prompt(self, data: dict) -> str:
        """Build plain-text clinical prompt — no roles, no special tokens."""
        parts = ["Clinical case analysis:\n"]
        if data.get("gestational_age"):
            parts.append(f"Gestational age: {data['gestational_age']} weeks")
        if data.get("hemoglobin"):
            parts.append(f"Hemoglobin: {data['hemoglobin']} g/dL")
        if data.get("bp_systolic") and data.get("bp_diastolic"):
            parts.append(f"Blood pressure: {data['bp_systolic']}/{data['bp_diastolic']} mmHg")
        if data.get("proteinuria"):
            parts.append(f"Proteinuria: {data['proteinuria']}")
        if data.get("hb_trend"):
            parts.append(f"Hemoglobin trend: {' → '.join(map(str, data['hb_trend']))} g/dL")
        parts.append("\nClinical assessment:")
        return "\n".join(parts)

    # ── Output parser (preserved from original — your Safety Net logic) ───────

    def _parse_reasoning_output(self, response: str, original_data: dict) -> dict:
        """
        Parse model response into structured format.
        Safety Net overrides are preserved exactly from original.
        """
        response_lower = response.lower()

        high_risk_conditions = [
            "preeclampsia", "pre-eclampsia", "eclampsia",
            "severe anemia", "severe hypertension", "hellp syndrome", "hellp",
            "placental abruption", "abruption", "fetal distress",
            "meets diagnostic criteria for preeclampsia",
            "diagnostic criteria for preeclampsia",
        ]
        moderate_risk_conditions = [
            "gestational hypertension", "mild anemia", "moderate anemia",
            "iron deficiency anemia", "iron deficiency", "stage 1 hypertension",
            "folate deficiency", "vitamin b12 deficiency",
        ]
        low_risk_indicators = [
            "normal", "low risk", "routine monitoring",
            "no immediate concern", "within normal limits",
        ]

        if any(c in response_lower for c in high_risk_conditions):
            risk = "HIGH"
        elif any(c in response_lower for c in moderate_risk_conditions):
            risk = "MODERATE"
        elif "high risk" in response_lower or "severe" in response_lower:
            risk = "HIGH"
        elif "moderate risk" in response_lower or "concerning" in response_lower:
            risk = "MODERATE"
        elif any(i in response_lower for i in low_risk_indicators):
            risk = "LOW"
        else:
            risk = "UNKNOWN"

        urgent_keywords = [
            "immediate", "urgent", "emergency", "preeclampsia", "pre-eclampsia",
            "eclampsia", "severe anemia", "hellp", "fetal distress",
            "severe hypertension", "placental abruption", "abruption",
            "immediate referral", "urgent referral",
        ]
        referral_urgent = any(k in response_lower for k in urgent_keywords) or risk == "HIGH"

        # ── Safety Net (deterministic overrides — DO NOT MODIFY) ──────────────
        safety_net_triggered = False

        if original_data.get("hemoglobin"):
            hb = original_data["hemoglobin"]
            if hb < 7.0:
                risk = "HIGH"; referral_urgent = True; safety_net_triggered = True
                logger.warning(f"Safety Net: Hb={hb} g/dL → HIGH")
            elif hb < 9.0 and risk in ["LOW", "UNKNOWN"]:
                risk = "HIGH"; referral_urgent = True; safety_net_triggered = True
                logger.warning(f"Safety Net: Hb={hb} g/dL → HIGH")

        if original_data.get("bp_systolic"):
            bp = original_data["bp_systolic"]
            if bp >= 160:
                risk = "HIGH"; referral_urgent = True; safety_net_triggered = True
                logger.warning(f"Safety Net: BP={bp} mmHg → HIGH")
            elif bp >= 150 and risk in ["LOW", "UNKNOWN"]:
                risk = "HIGH"; referral_urgent = True; safety_net_triggered = True
                logger.warning(f"Safety Net: BP={bp} mmHg → HIGH")

        proteinuria_significant = original_data.get("proteinuria") in [
            "+2", "++", "2+", "+++", "3+", "+3",
        ]
        bp_elevated = original_data.get("bp_systolic", 0) >= 140
        if proteinuria_significant and bp_elevated:
            risk = "HIGH"; referral_urgent = True; safety_net_triggered = True
            logger.warning("Safety Net: HTN + proteinuria → HIGH (pre-eclampsia criteria)")

        return {
            "risk_category":        risk,
            "reasoning":            response.strip(),
            "confidence":           "high" if risk != "UNKNOWN" else "low",
            "referral_urgent":      referral_urgent,
            "model_used":           f"MedGemma-1.5-4b-it ({self.backend})",
            "safety_net_triggered": safety_net_triggered,
        }
