export interface Patient {
  id: string
  name: string
  age: number
  phone: string
  village: string
  lmpDate: string
  createdAt: string
}

export interface ExtractedData {
  bp: string
  weight: string
  hemoglobin: string
  platelets: string
}

/** Backend may return a plain string OR a structured object */
export interface AiExplanation {
  text: string
  source?: string
  backend?: string
  [key: string]: unknown
}

/** A recommendation returned as an object from the new backend */
export interface RecommendationObj {
  action: string
  priority: 'urgent' | 'near-term' | 'follow-up'
  why: string
  practical_note?: string
  source?: string
}

export interface AssessmentResult {
  risk_level: "Low" | "Medium" | "High" | "LOW" | "MODERATE" | "HIGH" | "UNKNOWN"
  ai_explanation: string | AiExplanation
  recommendations: Array<string | RecommendationObj>
  extracted_data?: ExtractedData
  evidence_summary?: string[]
}

export type Symptom =
  | "headache"
  | "blurred_vision"
  | "pedal_edema"
  | "facial_edema"
  | "breathlessness"
  | "dizziness"
  | "reduced_fetal_movement"
  | "abdominal_pain"
  | "nausea_vomiting"
  | "none"

export interface Visit {
  id: string
  patientId: string
  date: string
  images: string[] // base64 encoded
  gestationalAgeWeeks: number
  symptoms: Symptom[]
  otherSymptoms?: string
  result?: AssessmentResult
}
