"use client"

import { useState, useCallback, useMemo } from "react"
import { useLanguage } from "./language-provider"
import { ImageUpload } from "./image-upload"
import { AssessmentResult } from "./assessment-result"
import { RiskBadge } from "./risk-badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog"
import {
  ArrowLeft,
  Plus,
  Calendar,
  User,
  Phone,
  MapPin,
  FileImage,
  Loader2,
  Pencil,
  Check,
} from "lucide-react"
import type { Patient, Visit, Symptom, AssessmentResult as AssessmentResultType } from "@/lib/types"
import { assessRisk, confirmLabs, type PendingConfirmation } from "@/lib/api"
import { addVisit, updateVisitResult, updatePatient } from "@/lib/store"
import { format, differenceInWeeks } from "date-fns"
import { LabConfirmationDialog, type ConfirmedLabValues } from "./lab-confirmation-dialog"

const ALL_SYMPTOMS: { key: Symptom; label: string }[] = [
  { key: "headache", label: "Headache" },
  { key: "blurred_vision", label: "Blurred Vision" },
  { key: "pedal_edema", label: "Foot / Leg Swelling" },
  { key: "facial_edema", label: "Face Swelling" },
  { key: "breathlessness", label: "Breathlessness" },
  { key: "dizziness", label: "Dizziness" },
  { key: "reduced_fetal_movement", label: "Reduced Fetal Movement" },
  { key: "abdominal_pain", label: "Abdominal Pain" },
  { key: "nausea_vomiting", label: "Nausea / Vomiting" },
  { key: "none", label: "None" },
]

/** Lookup map kept for the visit-history symptom chip list */
const SYMPTOM_LABEL: Record<Symptom, string> = Object.fromEntries(
  ALL_SYMPTOMS.map(({ key, label }) => [key, label])
) as Record<Symptom, string>

interface PatientDetailProps {
  patient: Patient
  visits: Visit[]
  onBack: () => void
  onUpdate: () => void
}

export function PatientDetail({
  patient,
  visits,
  onBack,
  onUpdate,
}: PatientDetailProps) {
  const { t } = useLanguage()
  const [showNewVisit, setShowNewVisit] = useState(false)
  const [images, setImages] = useState<string[]>([])
  const [selectedSymptoms, setSelectedSymptoms] = useState<Symptom[]>([])
  const [otherSymptoms, setOtherSymptoms] = useState("")
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [selectedVisitId, setSelectedVisitId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [pendingConfirmation, setPendingConfirmation] = useState<PendingConfirmation | null>(null)
  const [confirmLoading, setConfirmLoading] = useState(false)
  // Manual gestational age override — ANM can correct if LMP is uncertain
  const [manualGestationalAge, setManualGestationalAge] = useState<string>("")
  // Track visit id so confirmLabs can attach the result after confirmation
  const [pendingVisitId, setPendingVisitId] = useState<string | null>(null)

  // Visit mode: image upload or manual data entry
  const [visitMode, setVisitMode] = useState<"upload" | "manual">("upload")

  // Manual entry field state
  const [manualBpSys, setManualBpSys] = useState("")
  const [manualBpDia, setManualBpDia] = useState("")
  const [manualHb, setManualHb] = useState("")
  const [manualPlt, setManualPlt] = useState("")
  const [manualProto, setManualProto] = useState("nil")
  const [manualWeight, setManualWeight] = useState("")

  // Edit patient state
  const [editOpen, setEditOpen] = useState(false)
  const [editName, setEditName] = useState(patient.name)
  const [editPhone, setEditPhone] = useState(patient.phone)
  const [editLmp, setEditLmp] = useState(patient.lmpDate)
  const [editVillage, setEditVillage] = useState(patient.village)

  const gestationalWeeks = useMemo(() => {
    return differenceInWeeks(new Date(), new Date(patient.lmpDate))
  }, [patient.lmpDate])

  // Use manually entered GA if provided, otherwise fall back to LMP-derived
  const effectiveGestationalWeeks = useMemo(() => {
    const manual = parseInt(manualGestationalAge)
    if (!isNaN(manual) && manual >= 4 && manual <= 42) return manual
    return gestationalWeeks
  }, [manualGestationalAge, gestationalWeeks])

  const sortedVisits = useMemo(() => {
    return [...visits].sort(
      (a, b) => new Date(b.date).getTime() - new Date(a.date).getTime()
    )
  }, [visits])

  const selectedVisit = useMemo(() => {
    if (!selectedVisitId) return null
    return sortedVisits.find((v) => v.id === selectedVisitId) ?? null
  }, [selectedVisitId, sortedVisits])

  // Symptom toggle logic
  const handleToggleSymptom = useCallback((symptom: Symptom) => {
    setSelectedSymptoms((prev) => {
      if (symptom === "none") {
        // Selecting "none" clears all others
        return prev.includes("none") ? [] : ["none"]
      }
      // Selecting a real symptom removes "none"
      const withoutNone = prev.filter((s) => s !== "none")
      if (withoutNone.includes(symptom)) {
        return withoutNone.filter((s) => s !== symptom)
      }
      return [...withoutNone, symptom]
    })
  }, [])

  const handleAnalyze = useCallback(async () => {
    setIsAnalyzing(true)
    setError(null)

    const symptomsToSend =
      selectedSymptoms.length === 0 ? (["none"] as Symptom[]) : selectedSymptoms

    try {
      let response
      let visit

      if (visitMode === "manual") {
        // ── Manual entry: send values directly, no image required ──
        const ga = manualGestationalAge
          ? parseInt(manualGestationalAge)
          : effectiveGestationalWeeks
        visit = addVisit({
          patientId: patient.id,
          date: new Date().toISOString().split("T")[0],
          images: [],
          gestationalAgeWeeks: ga,
          symptoms: symptomsToSend,
          otherSymptoms: otherSymptoms.trim() || undefined,
        })
        response = await assessRisk(
          patient.id,
          ga,
          [],
          symptomsToSend,
          otherSymptoms.trim(),
          {
            bp_systolic: manualBpSys ? parseInt(manualBpSys) : undefined,
            bp_diastolic: manualBpDia ? parseInt(manualBpDia) : undefined,
            hemoglobin: manualHb ? parseFloat(manualHb) : undefined,
            platelets_per_ul: manualPlt ? parseInt(manualPlt) : undefined,
            proteinuria: manualProto,
            weight_kg: manualWeight ? parseFloat(manualWeight) : undefined,
          }
        )
      } else {
        // ── Upload mode: images required ──
        if (images.length === 0) {
          setError(t("imagesRequired"))
          setIsAnalyzing(false)
          return
        }
        visit = addVisit({
          patientId: patient.id,
          date: new Date().toISOString().split("T")[0],
          images,
          gestationalAgeWeeks: effectiveGestationalWeeks,
          symptoms: symptomsToSend,
          otherSymptoms: otherSymptoms.trim() || undefined,
        })
        response = await assessRisk(
          patient.id,
          effectiveGestationalWeeks,
          images,
          symptomsToSend,
          otherSymptoms.trim()
        )
      }

      // Backend returned a pending_confirmation — show the verify dialog
      if ("status" in response && response.status === "pending_confirmation") {
        setPendingVisitId(visit.id)
        setPendingConfirmation(response as PendingConfirmation)
        setIsAnalyzing(false)
        return
      }

      // Normal result — store and display
      updateVisitResult(visit.id, response as AssessmentResultType)
      setImages([])
      setSelectedSymptoms([])
      setOtherSymptoms("")
      setManualGestationalAge("")
      setManualBpSys(""); setManualBpDia("")
      setManualHb(""); setManualPlt("")
      setManualWeight(""); setManualProto("nil")
      setShowNewVisit(false)
      setSelectedVisitId(visit.id)
      onUpdate()
    } catch {
      setError(t("apiError"))
    } finally {
      setIsAnalyzing(false)
    }
  }, [
    visitMode, images, selectedSymptoms, otherSymptoms,
    patient.id, effectiveGestationalWeeks, manualGestationalAge,
    manualBpSys, manualBpDia, manualHb, manualPlt, manualProto, manualWeight,
    t, onUpdate,
  ])

  const handleSavePatient = useCallback(() => {
    updatePatient(patient.id, {
      name: editName.trim(),
      phone: editPhone.trim(),
      lmpDate: editLmp,
      village: editVillage.trim(),
    })
    setEditOpen(false)
    onUpdate()
  }, [patient.id, editName, editPhone, editLmp, editVillage, onUpdate])

  const openEditDialog = useCallback(() => {
    setEditName(patient.name)
    setEditPhone(patient.phone)
    setEditLmp(patient.lmpDate)
    setEditVillage(patient.village)
    setEditOpen(true)
  }, [patient])

  return (
    <div className="space-y-4">
      {/* Back button */}
      <Button
        variant="ghost"
        onClick={onBack}
        className="text-primary hover:text-primary hover:bg-accent gap-1.5"
      >
        <ArrowLeft className="h-4 w-4" />
        {t("back")}
      </Button>

      {/* Patient info card */}
      <Card className="shadow-sm border-border">
        <CardHeader className="pb-3 border-b border-border bg-muted/30">
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2 text-foreground">
              <User className="h-5 w-5 text-primary" />
              {t("patientDetails")}
            </CardTitle>
            <Button
              variant="outline"
              size="sm"
              onClick={openEditDialog}
              className="border-primary/30 text-primary hover:bg-accent hover:text-accent-foreground gap-1.5 bg-transparent"
            >
              <Pencil className="h-3.5 w-3.5" />
              {t("editPatient")}
            </Button>
          </div>
        </CardHeader>
        <CardContent className="pt-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide">
                {t("name")}
              </p>
              <p className="text-sm font-semibold text-foreground mt-0.5">
                {patient.name}
              </p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide">
                {t("age")}
              </p>
              <p className="text-sm font-semibold text-foreground mt-0.5">
                {patient.age}
              </p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide">
                {t("phone")}
              </p>
              <p className="text-sm text-foreground mt-0.5 flex items-center gap-1">
                <Phone className="h-3 w-3 text-muted-foreground" />
                {patient.phone}
              </p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide">
                {t("village")}
              </p>
              <p className="text-sm text-foreground mt-0.5 flex items-center gap-1">
                <MapPin className="h-3 w-3 text-muted-foreground" />
                {patient.village}
              </p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide">
                {t("lmpDate")}
              </p>
              <p className="text-sm text-foreground mt-0.5 flex items-center gap-1">
                <Calendar className="h-3 w-3 text-muted-foreground" />
                {format(new Date(patient.lmpDate), "dd MMM yyyy")}
              </p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide">
                {t("gestationalAge")}
              </p>
              <p className="text-sm font-semibold text-primary mt-0.5">
                {gestationalWeeks} {t("weeks")}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Visits section header */}
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-bold text-foreground">{t("visits")}</h3>
        {!showNewVisit && (
          <Button
            onClick={() => {
              setShowNewVisit(true)
              setSelectedVisitId(null)
            }}
            className="bg-primary text-primary-foreground hover:bg-primary/90"
            size="sm"
          >
            <Plus className="h-4 w-4 mr-1.5" />
            {t("newVisit")}
          </Button>
        )}
      </div>

      {/* New visit form */}
      {showNewVisit && (
        <Card className="shadow-sm border-primary/30 border-2">
          <CardHeader className="pb-3 border-b border-border bg-accent/30">
            <CardTitle className="text-base flex items-center gap-2 text-foreground">
              <FileImage className="h-4 w-4 text-primary" />
              {t("newVisit")}
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-4 space-y-5">

            {/* ── Mode tabs ── */}
            <div className="flex gap-2 border-b border-border pb-3">
              <button
                type="button"
                onClick={() => setVisitMode("upload")}
                className={`flex items-center gap-1.5 px-4 py-2 rounded-md text-sm font-medium transition-colors ${visitMode === "upload"
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                  }`}
              >
                📷 Upload Lab Report
              </button>
              <button
                type="button"
                onClick={() => setVisitMode("manual")}
                className={`flex items-center gap-1.5 px-4 py-2 rounded-md text-sm font-medium transition-colors ${visitMode === "manual"
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                  }`}
              >
                ✏️ Enter Manually
              </button>
            </div>

            {/* ── Symptom selector (shared by both modes) ── */}
            <div className="space-y-2">
              <Label className="text-sm font-semibold text-foreground">
                {t("symptoms")}
              </Label>
              <p className="text-xs text-muted-foreground">{t("selectSymptoms")}</p>
              <div className="flex flex-wrap gap-2">
                {ALL_SYMPTOMS.map(({ key, label }) => {
                  const isSelected = selectedSymptoms.includes(key)
                  return (
                    <button
                      key={key}
                      type="button"
                      onClick={() => handleToggleSymptom(key)}
                      className={`inline-flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-sm font-medium transition-colors ${isSelected
                          ? key === "none"
                            ? "border-success bg-success/10 text-success"
                            : "border-primary bg-primary/10 text-primary"
                          : "border-border bg-card text-foreground hover:bg-muted"
                        }`}
                    >
                      {isSelected && <Check className="h-3.5 w-3.5" />}
                      {label}
                    </button>
                  )
                })}
              </div>
              <div className="mt-3 space-y-1.5">
                <Label htmlFor="other-symptoms" className="text-sm font-medium text-foreground">
                  {t("otherSymptoms" as Parameters<typeof t>[0])}
                </Label>
                <textarea
                  id="other-symptoms"
                  value={otherSymptoms}
                  onChange={(e) => setOtherSymptoms(e.target.value)}
                  placeholder={t("otherSymptomsPlaceholder" as Parameters<typeof t>[0])}
                  rows={2}
                  className="flex w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 resize-none"
                />
              </div>
            </div>

            {/* ── UPLOAD MODE ── */}
            {visitMode === "upload" && (
              <div className="space-y-4">
                <ImageUpload images={images} onImagesChange={setImages} maxImages={5} />

                {/* GA override */}
                <div className="space-y-1">
                  <Label htmlFor="ga-manual" className="text-sm font-semibold text-foreground">
                    Gestational Age (weeks)
                    <span className="ml-2 text-xs font-normal text-muted-foreground">
                      LMP-derived: {gestationalWeeks} wks — override if uncertain
                    </span>
                  </Label>
                  <Input
                    id="ga-manual"
                    type="number"
                    min={4}
                    max={42}
                    value={manualGestationalAge}
                    onChange={(e) => setManualGestationalAge(e.target.value)}
                    placeholder={`Default: ${gestationalWeeks} wks (from LMP)`}
                    className="border-border bg-background text-foreground"
                  />
                  {manualGestationalAge && !isNaN(parseInt(manualGestationalAge)) && (
                    <p className="text-xs text-muted-foreground">
                      ≈ {(parseInt(manualGestationalAge) / 4.33).toFixed(1)} months
                      {" · "}Using{" "}
                      <span className="font-medium text-primary">
                        {parseInt(manualGestationalAge)} weeks
                      </span>{" "}
                      for assessment
                    </p>
                  )}
                </div>
              </div>
            )}

            {/* ── MANUAL ENTRY MODE ── */}
            {visitMode === "manual" && (
              <div className="space-y-4">
                <p className="text-sm text-muted-foreground">
                  Enter lab values directly — no image needed.
                </p>
                <div className="grid grid-cols-2 gap-4">

                  {/* BP Systolic */}
                  <div className="space-y-1">
                    <Label htmlFor="m-bpSys" className="text-sm font-medium">
                      BP Systolic (mmHg)
                    </Label>
                    <Input
                      id="m-bpSys"
                      type="number"
                      min={70}
                      max={220}
                      value={manualBpSys}
                      onChange={(e) => setManualBpSys(e.target.value)}
                      placeholder="e.g. 120"
                      className="border-border bg-background text-foreground"
                    />
                  </div>

                  {/* BP Diastolic */}
                  <div className="space-y-1">
                    <Label htmlFor="m-bpDia" className="text-sm font-medium">
                      BP Diastolic (mmHg)
                    </Label>
                    <Input
                      id="m-bpDia"
                      type="number"
                      min={40}
                      max={140}
                      value={manualBpDia}
                      onChange={(e) => setManualBpDia(e.target.value)}
                      placeholder="e.g. 80"
                      className="border-border bg-background text-foreground"
                    />
                  </div>

                  {/* Hemoglobin */}
                  <div className="space-y-1">
                    <Label htmlFor="m-hb" className="text-sm font-medium">
                      Hemoglobin (g/dL)
                    </Label>
                    <Input
                      id="m-hb"
                      type="number"
                      step={0.1}
                      min={3}
                      max={22}
                      value={manualHb}
                      onChange={(e) => setManualHb(e.target.value)}
                      placeholder="e.g. 11.5"
                      className="border-border bg-background text-foreground"
                    />
                  </div>

                  {/* Platelets */}
                  <div className="space-y-1">
                    <Label htmlFor="m-plt" className="text-sm font-medium">
                      Platelet Count (/µL)
                      {manualPlt && !isNaN(parseInt(manualPlt)) && (
                        <span className="ml-1 text-xs text-muted-foreground">
                          = {(parseInt(manualPlt) / 100000).toFixed(2)} lakh
                        </span>
                      )}
                    </Label>
                    <Input
                      id="m-plt"
                      type="number"
                      step={1000}
                      value={manualPlt}
                      onChange={(e) => setManualPlt(e.target.value)}
                      placeholder="e.g. 150000"
                      className="border-border bg-background text-foreground"
                    />
                  </div>

                  {/* Gestational Age */}
                  <div className="space-y-1">
                    <Label htmlFor="m-ga" className="text-sm font-medium">
                      Gestational Age (weeks)
                      <span className="ml-1 text-xs text-muted-foreground">
                        LMP: {gestationalWeeks} wks
                      </span>
                    </Label>
                    <Input
                      id="m-ga"
                      type="number"
                      min={4}
                      max={42}
                      value={manualGestationalAge}
                      onChange={(e) => setManualGestationalAge(e.target.value)}
                      placeholder={`Default: ${gestationalWeeks} wks`}
                      className="border-border bg-background text-foreground"
                    />
                    {manualGestationalAge && !isNaN(parseInt(manualGestationalAge)) && (
                      <p className="text-xs text-muted-foreground">
                        ≈ {(parseInt(manualGestationalAge) / 4.33).toFixed(1)} months
                      </p>
                    )}
                  </div>

                  {/* Proteinuria */}
                  <div className="space-y-1">
                    <Label htmlFor="m-proto" className="text-sm font-medium">
                      Proteinuria (urine test)
                    </Label>
                    <select
                      id="m-proto"
                      value={manualProto}
                      onChange={(e) => setManualProto(e.target.value)}
                      className="flex h-10 w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    >
                      <option value="nil">Nil (negative)</option>
                      <option value="+1">+1 (trace)</option>
                      <option value="+2">+2 (moderate)</option>
                      <option value="+3">+3 (severe)</option>
                    </select>
                  </div>

                  {/* Weight */}
                  <div className="space-y-1">
                    <Label htmlFor="m-weight" className="text-sm font-medium">
                      Weight (kg)
                    </Label>
                    <Input
                      id="m-weight"
                      type="number"
                      step={0.1}
                      min={30}
                      max={150}
                      value={manualWeight}
                      onChange={(e) => setManualWeight(e.target.value)}
                      placeholder="e.g. 58"
                      className="border-border bg-background text-foreground"
                    />
                  </div>

                </div>
              </div>
            )}

            {error && (
              <p className="text-sm text-destructive font-medium bg-destructive/10 px-3 py-2 rounded-md">
                {error}
              </p>
            )}

            <div className="flex gap-3">
              <Button
                onClick={handleAnalyze}
                disabled={isAnalyzing || (visitMode === "upload" && images.length === 0)}
                className="bg-primary text-primary-foreground hover:bg-primary/90 flex-1"
              >
                {isAnalyzing ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-1.5 animate-spin" />
                    {t("analyzing")}
                  </>
                ) : (
                  t("analyze")
                )}
              </Button>
              <Button
                variant="outline"
                onClick={() => {
                  setShowNewVisit(false)
                  setVisitMode("upload")
                  setImages([])
                  setSelectedSymptoms([])
                  setOtherSymptoms("")
                  setManualGestationalAge("")
                  setManualBpSys(""); setManualBpDia("")
                  setManualHb(""); setManualPlt("")
                  setManualWeight(""); setManualProto("nil")
                  setError(null)
                }}
                className="border-border text-foreground hover:bg-muted"
              >
                {t("cancel")}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Selected visit result */}
      {selectedVisit?.result && (
        <AssessmentResult
          result={selectedVisit.result}
          patientId={patient.id}
          visitDate={selectedVisit.date}
        />
      )}

      {/* Visit history */}
      {sortedVisits.length > 0 ? (
        <Card className="shadow-sm border-border">
          <CardHeader className="pb-3 border-b border-border bg-muted/30">
            <CardTitle className="text-base text-foreground">
              {t("visits")}
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <div className="divide-y divide-border">
              {sortedVisits.map((visit) => (
                <button
                  key={visit.id}
                  type="button"
                  onClick={() =>
                    setSelectedVisitId(
                      selectedVisitId === visit.id ? null : visit.id
                    )
                  }
                  className={`w-full px-4 py-3 flex items-center justify-between hover:bg-accent/50 transition-colors text-left ${selectedVisitId === visit.id ? "bg-accent" : ""
                    }`}
                >
                  <div className="flex items-center gap-3">
                    <Calendar className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                    <div>
                      <p className="text-sm font-medium text-foreground">
                        {format(new Date(visit.date), "dd MMM yyyy")}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {visit.gestationalAgeWeeks} {t("weeks")} |{" "}
                        {visit.images.length} {t("images")}
                        {visit.symptoms &&
                          visit.symptoms.length > 0 &&
                          !visit.symptoms.includes("none") && (
                            <>
                              {" | "}
                              {visit.symptoms
                                .map((s: Symptom) => SYMPTOM_LABEL[s] ?? s)
                                .join(", ")}
                              {visit.otherSymptoms && (
                                <>, {visit.otherSymptoms}</>
                              )}
                            </>
                          )}
                      </p>
                    </div>
                  </div>
                  {visit.result && (
                    <RiskBadge level={visit.result.risk_level} size="sm" />
                  )}
                </button>
              ))}
            </div>
          </CardContent>
        </Card>
      ) : (
        !showNewVisit && (
          <Card className="shadow-sm border-border">
            <CardContent className="py-10 text-center">
              <FileImage className="h-10 w-10 text-muted-foreground/40 mx-auto mb-2" />
              <p className="text-sm text-muted-foreground">{t("noVisits")}</p>
            </CardContent>
          </Card>
        )
      )}

      {/* Edit patient dialog */}
      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent className="sm:max-w-md bg-card text-foreground">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Pencil className="h-4 w-4 text-primary" />
              {t("editPatient")}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-1.5">
              <Label htmlFor="edit-name" className="text-sm font-medium text-foreground">
                {t("name")}
              </Label>
              <Input
                id="edit-name"
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                className="border-border bg-background text-foreground"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="edit-phone" className="text-sm font-medium text-foreground">
                {t("phone")}
              </Label>
              <Input
                id="edit-phone"
                value={editPhone}
                onChange={(e) => setEditPhone(e.target.value)}
                className="border-border bg-background text-foreground"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="edit-lmp" className="text-sm font-medium text-foreground">
                {t("lmpDate")}
              </Label>
              <Input
                id="edit-lmp"
                type="date"
                value={editLmp}
                onChange={(e) => setEditLmp(e.target.value)}
                className="border-border bg-background text-foreground"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="edit-village" className="text-sm font-medium text-foreground">
                {t("village")}
              </Label>
              <Input
                id="edit-village"
                value={editVillage}
                onChange={(e) => setEditVillage(e.target.value)}
                className="border-border bg-background text-foreground"
              />
            </div>
          </div>
          <DialogFooter className="flex gap-2">
            <Button
              variant="outline"
              onClick={() => setEditOpen(false)}
              className="border-border text-foreground hover:bg-muted"
            >
              {t("cancel")}
            </Button>
            <Button
              onClick={handleSavePatient}
              disabled={!editName.trim() || !editPhone.trim() || !editLmp || !editVillage.trim()}
              className="bg-primary text-primary-foreground hover:bg-primary/90"
            >
              {t("updatePatient")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Lab confirmation dialog — shown when backend returns pending_confirmation */}
      {pendingConfirmation && (
        <LabConfirmationDialog
          pending={pendingConfirmation}
          isLoading={confirmLoading}
          onCancel={() => {
            setPendingConfirmation(null)
            setPendingVisitId(null)
          }}
          onConfirm={async (values: ConfirmedLabValues) => {
            setConfirmLoading(true)
            try {
              const result = await confirmLabs(
                pendingConfirmation.confirmation_token,
                values.hemoglobin,
                values.platelets_per_ul,
                values.bp_systolic,
                values.bp_diastolic,
                values.gestational_age,
                values.proteinuria
              )
              if (pendingVisitId) {
                updateVisitResult(pendingVisitId, result)
                setSelectedVisitId(pendingVisitId)
              }
              setPendingConfirmation(null)
              setPendingVisitId(null)
              setImages([])
              setSelectedSymptoms([])
              setOtherSymptoms("")
              setShowNewVisit(false)
              onUpdate()
            } catch (err) {
              setError(err instanceof Error ? err.message : "Confirmation failed")
              setPendingConfirmation(null)
            } finally {
              setConfirmLoading(false)
            }
          }}
        />
      )}
    </div>
  )
}
