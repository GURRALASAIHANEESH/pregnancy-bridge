"use client"

import { useState, useCallback } from "react"
import { RiskBadge } from "./risk-badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Download, Brain, ClipboardList, Activity, ShieldAlert, Loader2 } from "lucide-react"
import type { AssessmentResult as AssessmentResultType, RecommendationObj } from "@/lib/types"

/* ── cleanExplanationText ──────────────────────────────────────────────────────
 * Strips code fences and deduplicates repeated lines/sentences.
 * Safety net against model looping even after max_tokens truncation.
 */
function cleanExplanationText(raw: string): string {
  // Strip markdown code fences (```json, ```text, ``` etc.)
  let text = raw
    .replace(/```[\w]*/g, '')
    .replace(/```/g, '')
    .trim()

  // Strip prompt-leakage phrases the model sometimes echoes verbatim
  text = text.replace(/\*\*Your response:\*\*/gi, '')
  text = text.replace(/Your response:/gi, '')
  text = text.replace(/Clinical explanation:/gi, '').trim()

  // Strip LaTeX/math-competition artefacts (Gemma base model contamination)
  // Note: use [\s\S] instead of . with s-flag — ES6 target doesn't support dotAll
  text = text.replace(/Final Answer:[\s\S]*$/gi, '').trim()
  text = text.replace(/\$\\boxed\{[\s\S]*?\}\$/g, '').trim()
  text = text.replace(/Revised explanation:/gi, '').trim()

  // Deduplicate lines — keep only first occurrence of each normalised line
  const seen = new Set<string>()
  const lines = text
    .split('\n')
    .filter((line) => line.trim() !== '')
    .filter((line) => {
      // Strip leading numbering ("1) ", "2. ", etc.) for comparison
      const normalised = line.replace(/^\d+[\).:]\s*/, '').trim().toLowerCase()
      if (normalised.length < 10) return true  // keep short lines (headings etc.)
      if (seen.has(normalised)) return false   // duplicate — drop
      seen.add(normalised)
      return true
    })

  return lines.join('\n')
}

/* ── ACTION_LABELS — human-readable labels for deterministic action keys ──────
 * Falls back to rec.action.replace(/_/g, ' ') for any unknown key.
 */
const ACTION_LABELS: Record<string, string> = {
  urgent_refer_facility: 'Urgent Referral — Facility',
  urgent_refer_hellp: 'Urgent Referral — HELLP Risk',
  urgent_refer_preeclampsia: 'Urgent Referral — Pre-eclampsia',
  urgent_refer_anemia: 'Urgent Referral — Severe Anaemia',
  near_term_refer_platelets: 'Referral — Low Platelets',
  near_term_cbc_iron: 'CBC + Iron Supplementation',
  repeat_essential_labs: 'Repeat Essential Labs',
  monitor_bp_home: 'Monitor BP at Home',
  repeat_bp_phc: 'Repeat BP at PHC',
  refer_high_risk: 'Refer — High Risk Pregnancy',
  phc_referral_moderate: 'PHC Referral — Moderate Risk',
  monitor_symptoms: 'Monitor Symptoms',
  routine_monitoring: 'Routine Antenatal Care',
}

/* ── normalizeRisk ─────────────────────────────────────────────────────────────
 * Backend sends "HIGH" | "LOW" | "MODERATE" (uppercase).
 * RiskBadge and our CSS classes expect "Low" | "Medium" | "High".
 */
function normalizeRisk(raw: string): "Low" | "Medium" | "High" | "Unknown" {
  const lower = (raw ?? "").toLowerCase()
  if (lower === "high") return "High"
  if (lower === "moderate" || lower === "medium") return "Medium"
  if (lower === "low") return "Low"
  return "Unknown"
}

/* ── param‑status helper ───────────────────────────────────────────────────── */
function getParamStatus(param: string, value: string): { status: string; color: string } {
  if (param === "bp") {
    const match = value.match(/(\d+)\/(\d+)/)
    if (match) {
      const sys = parseInt(match[1])
      const dia = parseInt(match[2])
      if (sys >= 140 || dia >= 90) return { status: "High", color: "text-destructive" }
      if (sys >= 130 || dia >= 85) return { status: "Borderline", color: "text-yellow-600" }
      return { status: "Normal", color: "text-green-600" }
    }
  }
  if (param === "hemoglobin") {
    const num = parseFloat(value)
    if (!isNaN(num)) {
      if (num < 7) return { status: "Severe", color: "text-destructive" }
      if (num < 11) return { status: "Low", color: "text-yellow-600" }
      return { status: "Normal", color: "text-green-600" }
    }
  }
  if (param === "platelets") {
    const num = parseFloat(value)
    if (!isNaN(num)) {
      if (num < 1) return { status: "Low", color: "text-destructive" }
      if (num < 1.5) return { status: "Borderline", color: "text-yellow-600" }
      return { status: "Normal", color: "text-green-600" }
    }
  }
  return { status: "Normal", color: "text-green-600" }
}

/* ── priority sort order & color map ───────────────────────────────────────── */
const PRIORITY_ORDER: Record<string, number> = { urgent: 0, "near-term": 1, "follow-up": 2 }
const PRIORITY_BADGE: Record<string, string> = {
  urgent: "bg-red-100 text-red-700 border-red-300",
  "near-term": "bg-yellow-100 text-yellow-700 border-yellow-300",
  "follow-up": "bg-green-100 text-green-700 border-green-300",
}

/* ── component ─────────────────────────────────────────────────────────────── */
interface AssessmentResultProps {
  result: AssessmentResultType
  patientId: string
  visitDate: string
}

export function AssessmentResult({ result, patientId, visitDate }: AssessmentResultProps) {
  const risk = normalizeRisk(result.risk_level)

  /* ── Language translation state ─────────────────────────────────────────── */
  type Lang = "en" | "te" | "hi"
  const LANGS: { code: Lang; label: string }[] = [
    { code: "en", label: "🇬🇧 English" },
    { code: "te", label: "🇮🇳 తెలుగు" },
    { code: "hi", label: "🇮🇳 हिंदी" },
  ]
  const [displayLang, setDisplayLang] = useState<Lang>("en")
  // Cache translated results per language so re-clicking doesn't re-fetch
  const [translationCache, setTranslationCache] = useState<Partial<Record<Lang, string>>>({})
  const [translating, setTranslating] = useState(false)

  /* ── export ─────────────────────────────────────────────────────────────── */
  function handleExport() {
    const exportData = {
      patient_id: patientId,
      visit_date: visitDate,
      assessment: result,
      exported_at: new Date().toISOString(),
    }
    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: "application/json" })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = `assessment_${patientId}_${visitDate}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  /* ── ai_explanation — always extract a plain string ─────────────────────── */
  const rawExplanationText: string = (() => {
    const raw =
      typeof result.ai_explanation === "string"
        ? result.ai_explanation
        : (result.ai_explanation as { text?: string } | null)?.text ?? ""
    // cleanExplanationText: strips code fences + deduplicates repeated lines
    return cleanExplanationText(raw)
  })()

  /* ── Translation via Google Translate free endpoint (no API key) ─────────── */
  const translateText = useCallback(async (targetLang: "te" | "hi") => {
    // Return cached result immediately if available
    if (translationCache[targetLang]) return
    setTranslating(true)
    try {
      const url =
        `https://translate.googleapis.com/translate_a/single` +
        `?client=gtx&sl=en&tl=${targetLang}&dt=t&q=${encodeURIComponent(rawExplanationText)}`
      const res = await fetch(url)
      const data = await res.json()
      // Response is nested arrays — flatten all translated segments
      const translated: string = (data[0] as [string][]).map((seg) => seg[0]).join("")
      setTranslationCache((prev) => ({ ...prev, [targetLang]: translated }))
    } catch {
      setTranslationCache((prev) => ({
        ...prev,
        [targetLang]: "Translation unavailable. " + rawExplanationText,
      }))
    } finally {
      setTranslating(false)
    }
  }, [rawExplanationText, translationCache])

  /* ── Paragraph list for the currently selected language ─────────────────── */
  const activeText =
    displayLang === "en"
      ? rawExplanationText
      : (translationCache[displayLang] ?? "")

  // Split on real newlines OR literal \n escape sequences (backend may send either).
  // Then deduplicate consecutive identical paragraphs to prevent visual repetition.
  const explanationParagraphs = activeText
    .split(/\n|\\n/)
    .map((line) => line.trim())
    .filter((line) => line !== "")
    .filter((line, idx, arr) => idx === 0 || line !== arr[idx - 1])

  /* ── evidence_summary (may or may not exist) ────────────────────────────── */
  const evidenceSummary: string[] = result.evidence_summary ?? []

  /* ── extracted data rows ────────────────────────────────────────────────── */
  const extractedRows = result.extracted_data
    ? [
      { key: "bp", label: "Blood Pressure", value: result.extracted_data.bp },
      { key: "weight", label: "Weight", value: result.extracted_data.weight },
      { key: "hemoglobin", label: "Hemoglobin", value: result.extracted_data.hemoglobin },
      { key: "platelets", label: "Platelets", value: result.extracted_data.platelets },
    ]
    : []

  /* ── recommendations: sort urgent first ─────────────────────────────────── */
  const sortedRecs = [...(result.recommendations ?? [])].sort((a, b) => {
    const pa = typeof a === "object" && a !== null ? PRIORITY_ORDER[(a as RecommendationObj).priority] ?? 9 : 9
    const pb = typeof b === "object" && b !== null ? PRIORITY_ORDER[(b as RecommendationObj).priority] ?? 9 : 9
    return pa - pb
  })

  /* ── risk‑based border color ────────────────────────────────────────────── */
  const borderColor =
    risk === "High"
      ? "border-l-destructive bg-destructive/5"
      : risk === "Medium"
        ? "border-l-yellow-500 bg-yellow-50/50"
        : "border-l-green-500 bg-green-50/50"

  return (
    <div className="space-y-4">
      {/* ── Risk level banner ─────────────────────────────────────────────── */}
      <Card className={`shadow-sm border-l-4 ${borderColor}`}>
        <CardContent className="py-4">
          <div className="flex items-center justify-between flex-wrap gap-3">
            <div className="flex items-center gap-3">
              <span className="text-sm font-medium text-foreground">Risk Level:</span>
              <RiskBadge level={risk} size="md" />
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={handleExport}
              className="border-border text-foreground hover:bg-muted bg-transparent"
            >
              <Download className="h-4 w-4 mr-1.5" />
              Export JSON
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* ── Extracted data table ──────────────────────────────────────────── */}
      {extractedRows.length > 0 && (
        <Card className="shadow-sm border-border">
          <CardHeader className="pb-3 border-b border-border bg-muted/30">
            <CardTitle className="text-base flex items-center gap-2 text-foreground">
              <Activity className="h-4 w-4 text-primary" />
              Extracted Data
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow className="bg-muted/20">
                  <TableHead className="text-foreground font-semibold">Parameter</TableHead>
                  <TableHead className="text-foreground font-semibold">Value</TableHead>
                  <TableHead className="text-foreground font-semibold">Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {extractedRows.map((row) => {
                  const paramStatus = getParamStatus(row.key, row.value)
                  return (
                    <TableRow key={row.key}>
                      <TableCell className="font-medium text-foreground">{row.label}</TableCell>
                      <TableCell className="text-foreground">{row.value}</TableCell>
                      <TableCell>
                        <span className={`font-medium ${paramStatus.color}`}>
                          {paramStatus.status}
                        </span>
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {/* ── AI Explanation — only rendered when there is actual text ─────────── */}
      {rawExplanationText.trim() !== "" && (
        <Card className="shadow-sm border-border">
          <CardHeader className="pb-3 border-b border-border bg-muted/30">
            <CardTitle className="text-base flex items-center gap-2 text-foreground">
              <Brain className="h-4 w-4 text-primary" />
              AI Explanation
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-4">
            {/* Language toggle */}
            <div className="flex flex-wrap gap-2 mb-4">
              {LANGS.map(({ code, label }) => (
                <button
                  key={code}
                  type="button"
                  onClick={() => {
                    setDisplayLang(code)
                    if (code !== "en") translateText(code)
                  }}
                  className={`px-3 py-1 rounded-full text-sm font-medium border transition-colors ${displayLang === code
                    ? "bg-primary text-primary-foreground border-primary"
                    : "bg-card text-muted-foreground border-border hover:border-primary hover:text-primary"
                    }`}
                >
                  {label}
                </button>
              ))}
              {translating && (
                <span className="flex items-center gap-1.5 text-xs text-muted-foreground self-center">
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  Translating…
                </span>
              )}
            </div>

            {/* Explanation body */}
            {translating ? (
              <p className="text-sm text-muted-foreground italic">
                Translating…
              </p>
            ) : (
              <div className="text-sm leading-relaxed text-foreground space-y-2">
                {explanationParagraphs.map((line, i) => (
                  <p key={i}>{line}</p>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* ── Evidence Summary ───────────────────────────────────────────────── */}
      {evidenceSummary.length > 0 && (
        <Card className="shadow-sm border-border">
          <CardHeader className="pb-3 border-b border-border bg-muted/30">
            <CardTitle className="text-base flex items-center gap-2 text-foreground">
              <ShieldAlert className="h-4 w-4 text-primary" />
              Why this risk level?
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-4">
            <ul className="list-disc list-inside space-y-1.5 text-sm text-foreground">
              {evidenceSummary.map((item, i) => (
                <li key={i} className="leading-relaxed">{item}</li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {/* ── Recommendations ────────────────────────────────────────────────── */}
      <Card className="shadow-sm border-border">
        <CardHeader className="pb-3 border-b border-border bg-muted/30">
          <CardTitle className="text-base flex items-center gap-2 text-foreground">
            <ClipboardList className="h-4 w-4 text-primary" />
            Recommendations
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-4">
          <ol className="space-y-3">
            {sortedRecs.map((rec, i) => {
              const isObj = rec !== null && typeof rec === "object"
              const recObj = isObj ? (rec as RecommendationObj) : null

              if (recObj) {
                const badgeClass = PRIORITY_BADGE[recObj.priority] ?? "bg-muted text-muted-foreground"
                return (
                  <li key={`rec-${i}`} className="flex gap-3 text-sm">
                    <span className="flex-shrink-0 flex items-center justify-center h-5 w-5 rounded-full bg-primary/10 text-primary text-xs font-bold mt-0.5">
                      {i + 1}
                    </span>
                    <div className="space-y-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-semibold text-foreground">
                          {ACTION_LABELS[recObj.action] ?? recObj.action.replace(/_/g, ' ')}
                        </span>
                        <Badge
                          variant="outline"
                          className={`text-xs capitalize ${badgeClass}`}
                        >
                          {recObj.priority}
                        </Badge>
                      </div>
                      {recObj.why && (
                        <p className="text-muted-foreground leading-relaxed">{recObj.why}</p>
                      )}
                      {recObj.practical_note && (
                        <p className="text-muted-foreground italic leading-relaxed">
                          {recObj.practical_note}
                        </p>
                      )}
                    </div>
                  </li>
                )
              }

              /* Legacy: plain string recommendation */
              const text = String(rec)
              const isUrgent = text.startsWith("URGENT") || text.startsWith("ALERT")
              return (
                <li
                  key={`rec-${i}`}
                  className={`flex gap-3 text-sm ${isUrgent ? "text-destructive font-semibold" : "text-foreground"}`}
                >
                  <span className="flex-shrink-0 flex items-center justify-center h-5 w-5 rounded-full bg-primary/10 text-primary text-xs font-bold mt-0.5">
                    {i + 1}
                  </span>
                  <span className="leading-relaxed">{text}</span>
                </li>
              )
            })}
          </ol>
        </CardContent>
      </Card>
    </div>
  )
}
