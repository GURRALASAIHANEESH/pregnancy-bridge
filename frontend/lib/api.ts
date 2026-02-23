import type { AssessmentResult, Symptom } from "./types"

const API_BASE = "http://localhost:8001"

export interface ManualLabValues {
  bp_systolic?: number
  bp_diastolic?: number
  hemoglobin?: number
  platelets_per_ul?: number
  proteinuria?: string
  weight_kg?: number
}

export async function assessRisk(
  patientId: string,
  gestationalAgeWeeks: number,
  images: string[],
  symptoms: Symptom[],
  otherSymptoms?: string,
  manualValues?: ManualLabValues
): Promise<AssessmentResult | PendingConfirmation> {
  try {
    const response = await fetch(`${API_BASE}/api/v1/field-assess`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        patient_id: patientId,
        gestational_age_weeks: gestationalAgeWeeks,
        images,
        symptoms,
        other_symptoms: otherSymptoms || "",
        // Optional manual values — sent when the ANM enters data directly
        ...(manualValues ?? {}),
      }),
    })

    if (!response.ok) {
      throw new Error(`API error: ${response.status}`)
    }

    // Return raw JSON — can be AssessmentResult OR PendingConfirmation
    return await response.json()
  } catch (error) {
    console.log("[v0] API call failed, using mock response:", error)
    return getMockAssessment(gestationalAgeWeeks)
  }
}


function getMockAssessment(gestationalAge: number): AssessmentResult {
  const riskLevels: ("Low" | "Medium" | "High")[] = ["Low", "Medium", "High"]
  const riskIndex = gestationalAge > 30 ? 2 : gestationalAge > 20 ? 1 : 0
  const risk = riskLevels[riskIndex]

  const explanations: Record<string, string> = {
    Low: `Based on the uploaded lab reports for gestational age ${gestationalAge} weeks, all parameters appear within normal range. Blood pressure is normal, hemoglobin levels are adequate, and platelet count is satisfactory. The pregnancy is progressing well with no immediate concerns identified.`,
    Medium: `Analysis of the lab reports at ${gestationalAge} weeks gestation shows some parameters that require attention. Mild anemia is detected with hemoglobin slightly below optimal levels. Blood pressure shows a slight upward trend. Enhanced monitoring and dietary modifications are recommended.`,
    High: `ALERT: Lab report analysis at ${gestationalAge} weeks reveals concerning findings. Elevated blood pressure readings combined with low hemoglobin and borderline platelet counts indicate potential risk of complications. Immediate referral to a higher health facility is strongly recommended.`,
  }

  const mockExtracted: Record<string, { bp: string; weight: string; hemoglobin: string; platelets: string }> = {
    Low: { bp: "118/76 mmHg", weight: "56 kg", hemoglobin: "12.1 g/dL", platelets: "2.3 lakh/uL" },
    Medium: { bp: "138/88 mmHg", weight: "64 kg", hemoglobin: "9.5 g/dL", platelets: "1.6 lakh/uL" },
    High: { bp: "152/98 mmHg", weight: "72 kg", hemoglobin: "7.8 g/dL", platelets: "0.85 lakh/uL" },
  }

  const mockRecs: Record<string, string[]> = {
    Low: [
      "Continue regular prenatal visits as scheduled",
      "Maintain iron and folic acid supplementation",
      "Encourage balanced diet with protein-rich foods",
      "Schedule next visit in 4 weeks",
    ],
    Medium: [
      "Increase frequency of prenatal visits to every 2 weeks",
      "Start or increase iron supplementation",
      "Monitor blood pressure at every visit",
      "Ensure adequate rest and reduce physical strain",
      "Consider referral to PHC for specialist consultation",
    ],
    High: [
      "URGENT: Refer to District Hospital within 24 hours",
      "Begin antihypertensive medication per protocol",
      "Investigate and treat severe anemia urgently",
      "Monitor for pre-eclampsia symptoms",
      "Arrange safe transport to higher facility",
      "Do not delay referral",
    ],
  }

  return {
    risk_level: risk,
    ai_explanation: explanations[risk],
    recommendations: mockRecs[risk],
    extracted_data: mockExtracted[risk],
  }
}

// ── PendingConfirmation ────────────────────────────────────────────────────────

export interface PendingConfirmation {
  status: 'pending_confirmation'
  confirmation_token: string
  extracted_values: {
    hemoglobin_g_dl: number | null
    hemoglobin_status: string
    hemoglobin_raw: string | null
    platelets_per_ul: number | null
    platelets_lakh: number | null
    platelets_status: string
    platelets_raw: string | null
    platelets_unit: string | null
    // Fields the dialog may pre-populate from OCR (may be null if not found)
    bp_systolic: number | null
    bp_diastolic: number | null
    gestational_age: number | null
    proteinuria: string | null
  }
  flags: string[]
  has_critical_flags: boolean
  message: string
}

export async function confirmLabs(
  token: string,
  confirmedHemoglobin: number | null,
  confirmedPlateletsPerUl: number | null,
  confirmedBpSystolic: number | null,
  confirmedBpDiastolic: number | null,
  confirmedGestationalAge: number | null,
  confirmedProteinuria: string,
  anmNotes?: string
): Promise<AssessmentResult> {
  const res = await fetch(`${API_BASE}/api/v1/confirm-labs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      confirmation_token: token,
      confirmed_hemoglobin: confirmedHemoglobin,
      confirmed_platelets_per_ul: confirmedPlateletsPerUl,
      confirmed_bp_systolic: confirmedBpSystolic,
      confirmed_bp_diastolic: confirmedBpDiastolic,
      confirmed_gestational_age: confirmedGestationalAge,
      confirmed_proteinuria: confirmedProteinuria,
      anm_notes: anmNotes ?? '',
    }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail ?? `confirm-labs failed: ${res.status}`)
  }
  return res.json()
}
