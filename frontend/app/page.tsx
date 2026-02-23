"use client"

import { useState, useEffect, useCallback } from "react"
import { LanguageProvider } from "@/components/language-provider"
import { AppHeader } from "@/components/app-header"
import { PatientList } from "@/components/patient-list"
import { NewPatientForm } from "@/components/new-patient-form"
import { PatientDetail } from "@/components/patient-detail"
import {
  seedDemoData,
  getAllPatientsWithLatestVisit,
  addPatient,
  getPatient,
  getVisits,
} from "@/lib/store"
import type { Patient, Visit } from "@/lib/types"

type View = "list" | "new-patient" | "patient-detail"

function AppContent() {
  const [view, setView] = useState<View>("list")
  const [patients, setPatients] = useState<(Patient & { latestVisit?: Visit })[]>([])
  const [selectedPatientId, setSelectedPatientId] = useState<string | null>(null)
  const [selectedPatient, setSelectedPatient] = useState<Patient | null>(null)
  const [patientVisits, setPatientVisits] = useState<Visit[]>([])

  const loadPatients = useCallback(() => {
    const data = getAllPatientsWithLatestVisit()
    setPatients(data)
  }, [])

  useEffect(() => {
    seedDemoData()
    loadPatients()
  }, [loadPatients])

  const loadPatientDetail = useCallback((id: string) => {
    const patient = getPatient(id)
    if (patient) {
      setSelectedPatient(patient)
      setPatientVisits(getVisits(id))
    }
  }, [])

  const handleViewPatient = useCallback(
    (id: string) => {
      setSelectedPatientId(id)
      loadPatientDetail(id)
      setView("patient-detail")
    },
    [loadPatientDetail]
  )

  const handleNewPatient = useCallback(
    (data: { name: string; age: number; phone: string; village: string; lmpDate: string }) => {
      const patient = addPatient(data)
      loadPatients()
      handleViewPatient(patient.id)
    },
    [loadPatients, handleViewPatient]
  )

  const handleBackToList = useCallback(() => {
    loadPatients()
    setView("list")
    setSelectedPatientId(null)
    setSelectedPatient(null)
  }, [loadPatients])

  const handlePatientUpdate = useCallback(() => {
    if (selectedPatientId) {
      loadPatientDetail(selectedPatientId)
    }
    loadPatients()
  }, [selectedPatientId, loadPatientDetail, loadPatients])

  return (
    <div className="min-h-screen flex flex-col">
      <AppHeader />
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 py-6">
        {view === "list" && (
          <PatientList
            patients={patients}
            onNewPatient={() => setView("new-patient")}
            onViewPatient={handleViewPatient}
          />
        )}
        {view === "new-patient" && (
          <NewPatientForm
            onSave={handleNewPatient}
            onCancel={handleBackToList}
          />
        )}
        {view === "patient-detail" && selectedPatient && (
          <PatientDetail
            patient={selectedPatient}
            visits={patientVisits}
            onBack={handleBackToList}
            onUpdate={handlePatientUpdate}
          />
        )}
      </main>
      <footer className="border-t border-border bg-card py-3">
        <div className="max-w-7xl mx-auto px-4 text-center">
          <p className="text-xs text-muted-foreground">
            {"National Health Mission | Ministry of Health & Family Welfare | Government of India"}
          </p>
        </div>
      </footer>
    </div>
  )
}

export default function Page() {
  return (
    <LanguageProvider>
      <AppContent />
    </LanguageProvider>
  )
}
