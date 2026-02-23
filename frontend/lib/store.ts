import type { Patient, Visit, AssessmentResult } from "./types"

// localStorage-based store for offline support (as requested in spec)
const PATIENTS_KEY = "pra_patients"
const VISITS_KEY = "pra_visits"

function getFromStorage<T>(key: string, fallback: T): T {
  if (typeof window === "undefined") return fallback
  try {
    const data = localStorage.getItem(key)
    return data ? JSON.parse(data) : fallback
  } catch {
    return fallback
  }
}

function setToStorage<T>(key: string, data: T): void {
  if (typeof window === "undefined") return
  localStorage.setItem(key, JSON.stringify(data))
}

export function getPatients(): Patient[] {
  return getFromStorage<Patient[]>(PATIENTS_KEY, [])
}

export function addPatient(patient: Omit<Patient, "id" | "createdAt">): Patient {
  const patients = getPatients()
  const newPatient: Patient = {
    ...patient,
    id: `PAT_${Date.now()}_${Math.random().toString(36).slice(2, 7).toUpperCase()}`,
    createdAt: new Date().toISOString(),
  }
  patients.push(newPatient)
  setToStorage(PATIENTS_KEY, patients)
  return newPatient
}

export function getPatient(id: string): Patient | undefined {
  return getPatients().find((p) => p.id === id)
}

export function updatePatient(
  id: string,
  updates: Partial<Pick<Patient, "name" | "phone" | "lmpDate" | "village">>
): Patient | undefined {
  const patients = getPatients()
  const index = patients.findIndex((p) => p.id === id)
  if (index === -1) return undefined
  patients[index] = { ...patients[index], ...updates }
  setToStorage(PATIENTS_KEY, patients)
  return patients[index]
}

export function getVisits(patientId: string): Visit[] {
  const allVisits = getFromStorage<Visit[]>(VISITS_KEY, [])
  return allVisits.filter((v) => v.patientId === patientId)
}

export function addVisit(visit: Omit<Visit, "id">): Visit {
  const allVisits = getFromStorage<Visit[]>(VISITS_KEY, [])
  const newVisit: Visit = {
    ...visit,
    id: `VIS_${Date.now()}_${Math.random().toString(36).slice(2, 7).toUpperCase()}`,
  }
  allVisits.push(newVisit)
  setToStorage(VISITS_KEY, allVisits)
  return newVisit
}

export function updateVisitResult(visitId: string, result: AssessmentResult): void {
  const allVisits = getFromStorage<Visit[]>(VISITS_KEY, [])
  const index = allVisits.findIndex((v) => v.id === visitId)
  if (index !== -1) {
    allVisits[index].result = result
    setToStorage(VISITS_KEY, allVisits)
  }
}

export function getLatestVisit(patientId: string): Visit | undefined {
  const visits = getVisits(patientId)
  if (visits.length === 0) return undefined
  return visits.sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime())[0]
}

export function getAllPatientsWithLatestVisit(): (Patient & { latestVisit?: Visit })[] {
  const patients = getPatients()
  return patients.map((p) => ({
    ...p,
    latestVisit: getLatestVisit(p.id),
  }))
}

// Seed demo data
export function seedDemoData(): void {
  const patients = getPatients()
  if (patients.length > 0) return

  const demoPatients: Omit<Patient, "id" | "createdAt">[] = [
    { name: "Lakshmi Devi", age: 24, phone: "9876543210", village: "Kondapur", lmpDate: "2025-08-15" },
    { name: "Sarita Kumari", age: 28, phone: "9876543211", village: "Ramagundam", lmpDate: "2025-07-20" },
    { name: "Padma Rani", age: 22, phone: "9876543212", village: "Mancherial", lmpDate: "2025-09-01" },
    { name: "Kavitha Bai", age: 30, phone: "9876543213", village: "Nirmal", lmpDate: "2025-06-10" },
    { name: "Anjali Devi", age: 26, phone: "9876543214", village: "Adilabad", lmpDate: "2025-08-25" },
  ]

  const addedPatients = demoPatients.map((p) => addPatient(p))

  // Add demo visits
  const demoVisits: { patientIndex: number; visit: Omit<Visit, "id"> }[] = [
    {
      patientIndex: 0,
      visit: {
        patientId: "",
        date: "2025-12-10",
        images: [],
        gestationalAgeWeeks: 17,
        symptoms: ["none"],
        result: {
          risk_level: "Low",
          ai_explanation:
            "Based on the lab reports analysis, the patient shows normal blood pressure (120/80 mmHg), adequate hemoglobin levels (11.5 g/dL), and normal platelet count. All parameters are within the expected range for 17 weeks of gestation.",
          recommendations: [
            "Continue regular prenatal checkups",
            "Maintain iron and folic acid supplementation",
            "Schedule next visit in 4 weeks",
            "Monitor weight gain pattern",
          ],
          extracted_data: {
            bp: "120/80 mmHg",
            weight: "58 kg",
            hemoglobin: "11.5 g/dL",
            platelets: "2.1 lakh/uL",
          },
        },
      },
    },
    {
      patientIndex: 1,
      visit: {
        patientId: "",
        date: "2025-11-25",
        images: [],
        gestationalAgeWeeks: 22,
        symptoms: ["headache", "swelling"],
        result: {
          risk_level: "Medium",
          ai_explanation:
            "The patient presents with mildly elevated blood pressure (135/90 mmHg) and slightly low hemoglobin (9.8 g/dL), indicating mild anemia. While platelets are normal, close monitoring is advised. The combination of mild hypertension and anemia warrants increased surveillance.",
          recommendations: [
            "Increase iron supplementation dosage",
            "Monitor blood pressure twice weekly",
            "Schedule follow-up in 2 weeks",
            "Refer to PHC if BP remains elevated",
            "Ensure adequate protein intake",
          ],
          extracted_data: {
            bp: "135/90 mmHg",
            weight: "62 kg",
            hemoglobin: "9.8 g/dL",
            platelets: "1.8 lakh/uL",
          },
        },
      },
    },
    {
      patientIndex: 3,
      visit: {
        patientId: "",
        date: "2025-12-01",
        images: [],
        gestationalAgeWeeks: 30,
        symptoms: ["headache", "vision_blurring", "epigastric_pain"],
        result: {
          risk_level: "High",
          ai_explanation:
            "ALERT: The patient shows significantly elevated blood pressure (155/100 mmHg) along with low hemoglobin (7.5 g/dL) and reduced platelet count (90,000/uL). This combination of findings suggests a risk of pre-eclampsia and severe anemia. Immediate referral to a higher center is strongly recommended.",
          recommendations: [
            "URGENT: Refer to District Hospital immediately",
            "Start antihypertensive medication as per protocol",
            "Blood transfusion may be required for severe anemia",
            "Monitor for symptoms of pre-eclampsia (headache, visual disturbances, edema)",
            "Do not delay transport",
            "Keep patient in left lateral position during transport",
          ],
          extracted_data: {
            bp: "155/100 mmHg",
            weight: "70 kg",
            hemoglobin: "7.5 g/dL",
            platelets: "0.9 lakh/uL",
          },
        },
      },
    },
  ]

  for (const dv of demoVisits) {
    addVisit({
      ...dv.visit,
      patientId: addedPatients[dv.patientIndex].id,
    })
  }
}
