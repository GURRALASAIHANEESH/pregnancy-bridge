# PregnancyBridge

An offline-first maternal health risk assessment tool for ANMs (Auxiliary Nurse Midwives) at rural sub-centres in India. The ANM enters a pregnant woman's vitals and lab values — the app runs WHO-based clinical rules + MedGemma 4B AI and tells her whether the patient needs urgent referral, closer monitoring, or routine care. No internet required after setup.

---

## The Problem

India has 600 million ANC (antenatal care) visits per year. In rural sub-centres, ANMs assess pregnant women referred by ASHA community health workers — but have no clinical decision support tool. They rely on memory and judgment alone, with no doctor on-site.

57% of maternal deaths in India are preventable with early detection of pre-eclampsia, severe anemia, and thrombocytopenia.

PregnancyBridge gives the ANM an AI-assisted risk assessment in under 30 seconds, fully offline, on a basic laptop.

---

## What It Does

### Input — Two Ways to Enter Data

**Option 1: Upload a CBC lab report photo**
- ANM photographs the printed CBC report
- Tesseract OCR automatically extracts Hb and platelet values
- A confirmation dialog shows the extracted values
- ANM verifies or corrects them before the assessment runs

**Option 2: Manual entry**
- ANM types BP (systolic/diastolic), Hb, platelets, gestational age, proteinuria, weight
- Checks symptom boxes: headache, blurred vision, pedal edema, facial edema, dizziness, breathlessness, reduced fetal movement, abdominal pain, nausea/vomiting

### Risk Engine — Two Layers

| Layer | Role | Authority |
|---|---|---|
| Safety Net (WHO rules) | Deterministic rule-based engine, always runs | Final risk level — authoritative |
| MedGemma 4B GGUF | AI clinical explanation generator | Advisory only — never overrides rules |

### Output — What the ANM Sees
- Risk level: LOW / MODERATE / HIGH
- Clinical evidence (e.g. "Blood Pressure: Stage 2 hypertension")
- AI explanation from MedGemma
- Actionable recommendations (e.g. "URGENT: Immediate referral for severe hypertension")
- Language toggle: English / Telugu / Hindi

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11, FastAPI, uvicorn |
| AI Inference | llama-cpp-python (GGUF, CPU) |
| OCR | Tesseract OCR |
| Frontend | Next.js 16, TypeScript, Tailwind CSS v3, shadcn/ui |
| Risk Engine | Custom WHO-based deterministic rules |

**API Endpoints:**
- `POST /api/v1/field-assess` — main risk assessment (manual entry or no images)
- `POST /api/v1/confirm-labs` — confirm OCR-extracted lab values, then run assessment
- `GET /api/v1/health` — backend + model status

---

## Model

**Model:** medgemma-1.5-4b-it.Q4_K_M.gguf  
**Source:** https://huggingface.co/bartowski/medgemma-1.5-4b-it-GGUF  
**Size:** ~2.5 GB  
**Inference:** ~30 seconds on CPU (Intel i5)  
**RAM needed:** ~3 GB  
**Settings:** n_ctx=4096, n_threads=dynamic (all physical cores), temperature=0.0

### Download and Configure the Model

1. Download `medgemma-1.5-4b-it.Q4_K_M.gguf` from the link above, or use the helper script:

```python
from huggingface_hub import hf_hub_download
hf_hub_download(
    repo_id='bartowski/medgemma-1.5-4b-it-GGUF',
    filename='medgemma-1.5-4b-it-Q4_K_M.gguf',
    local_dir=r'D:/huggingface_cache'
)
```

2. Open `backend/pregnancy_bridge/modules/medgemma_extractor.py` and update the path at the top of the file:

```python
HF_CACHE_DIR = Path(r"D:\huggingface_cache")   # ← change to your actual directory
GGUF_PATH    = HF_CACHE_DIR / "medgemma-1.5-4b-it.Q4_K_M.gguf"
```

> The model file is NOT included in this repo (2.5 GB). It must be downloaded separately.

---

## Requirements

- Python 3.11+
- Node.js 18+
- Tesseract OCR installed and added to PATH
- ~3 GB RAM free
- Windows (tested on Windows 11, Intel i5)

---

## Run the Backend

```bash
cd backend
pip install -r requirements.txt
python app.py
```

Backend starts on: http://localhost:8001

On startup, MedGemma loads in a background thread (takes ~60-120s on CPU).  
Until it loads, the Safety Net rule engine handles all assessments automatically.

## Run the Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend starts on: http://localhost:3000

---

## Offline Usage

- 100% offline after the one-time model download.
- No API keys. No cloud. No internet needed during use.
- The deterministic Safety Net always runs — MedGemma is an enhancement, not a dependency.

---

## Project Structure

```
pregnancy-bridge/
├── backend/
│   ├── app.py                          # FastAPI app, port 8001
│   └── pregnancy_bridge/
│       └── modules/
│           ├── medgemma_extractor.py   # GGUF inference singleton + model path config
│           ├── medgemma_bridge.py      # QC gate + prompt builder
│           ├── risk_engine.py          # Primary WHO deterministic rules
│           ├── symptom_risk_engine.py  # Symptom-aware risk engine
│           ├── deterministic_recommender.py
│           ├── symptom_intake.py
│           ├── ocr_utils.py            # Tesseract OCR
│           └── clinical_parser.py     # Field extractor
└── frontend/
    ├── app/
    ├── components/
    │   ├── patient-detail.tsx          # Main form: upload + manual tabs
    │   ├── assessment-result.tsx       # Risk display + language toggle
    │   ├── lab-confirmation-dialog.tsx # OCR value confirmation
    │   └── risk-badge.tsx
    └── lib/
        ├── api.ts                      # assessRisk, confirmLabs
        ├── types.ts
        └── store.ts
```

---

## Submitted To

Kaggle MedGemma Impact Challenge  
Track: Main Track + Edge of AI Prize (offline CPU deployment)
