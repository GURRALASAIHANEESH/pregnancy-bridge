'use client'

import { useState } from 'react'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { AlertTriangle, CheckCircle } from 'lucide-react'
import type { PendingConfirmation } from '@/lib/api'

export interface ConfirmedLabValues {
  hemoglobin: number | null
  platelets_per_ul: number | null
  bp_systolic: number | null
  bp_diastolic: number | null
  gestational_age: number | null
  proteinuria: string
}

interface Props {
  pending: PendingConfirmation
  onConfirm: (values: ConfirmedLabValues) => Promise<void>
  onCancel: () => void
  isLoading: boolean
}

export function LabConfirmationDialog({ pending, onConfirm, onCancel, isLoading }: Props) {
  const ev = pending.extracted_values

  const [hb, setHb] = useState(ev.hemoglobin_g_dl != null ? String(ev.hemoglobin_g_dl) : '')
  const [plt, setPlt] = useState(ev.platelets_per_ul != null ? String(ev.platelets_per_ul) : '')
  const [bpSys, setBpSys] = useState(ev.bp_systolic != null ? String(ev.bp_systolic) : '')
  const [bpDia, setBpDia] = useState(ev.bp_diastolic != null ? String(ev.bp_diastolic) : '')
  const [ga, setGa] = useState(ev.gestational_age != null ? String(ev.gestational_age) : '')
  const [proto, setProto] = useState(ev.proteinuria ?? 'nil')

  const hasCritical = pending.has_critical_flags
  const criticalFlags = pending.flags.filter(f =>
    f.toLowerCase().includes('critical') || f.toLowerCase().includes('urgent')
  )

  function handleConfirm() {
    onConfirm({
      hemoglobin: hb.trim() ? parseFloat(hb) : null,
      platelets_per_ul: plt.trim() ? parseInt(plt) : null,
      bp_systolic: bpSys.trim() ? parseInt(bpSys) : null,
      bp_diastolic: bpDia.trim() ? parseInt(bpDia) : null,
      gestational_age: ga.trim() ? parseInt(ga) : null,
      proteinuria: proto,
    })
  }

  return (
    <Dialog open onOpenChange={open => { if (!open && !isLoading) onCancel() }}>
      <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-base">
            {hasCritical
              ? <AlertTriangle className="text-red-600 h-5 w-5 shrink-0" />
              : <CheckCircle className="text-green-600 h-5 w-5 shrink-0" />
            }
            Verify Extracted Lab Values
          </DialogTitle>
        </DialogHeader>

        {/* Critical banner */}
        {hasCritical && (
          <Alert variant="destructive">
            <AlertTriangle className="h-4 w-4" />
            <AlertDescription>
              <strong>⚠️ Critical values detected — verify before proceeding</strong>
              {criticalFlags.length > 0 && (
                <ul className="mt-1 list-disc list-inside text-sm">
                  {criticalFlags.map((f, i) => (
                    <li key={i}>{f.replace(/^CRITICAL:\s*/i, '')}</li>
                  ))}
                </ul>
              )}
            </AlertDescription>
          </Alert>
        )}

        <p className="text-sm text-muted-foreground">
          Values read from the lab report image. Edit any that look wrong,
          fill in missing ones, then tap <strong>Confirm & Assess</strong>.
        </p>

        <div className="grid grid-cols-2 gap-4">

          {/* Hemoglobin */}
          <div className="space-y-1">
            <Label htmlFor="hb">
              Hemoglobin (g/dL)
              {ev.hemoglobin_status === 'corrected' && (
                <span className="ml-1 text-xs text-yellow-600">
                  corrected from &quot;{ev.hemoglobin_raw}&quot;
                </span>
              )}
              {ev.hemoglobin_status === 'not_found' && (
                <span className="ml-1 text-xs text-red-500">not found in image</span>
              )}
            </Label>
            <Input id="hb" type="number" step="0.1" min="3" max="22"
              value={hb} onChange={e => setHb(e.target.value)}
              placeholder="e.g. 11.5"
              className={!hb ? 'border-yellow-400' : ''}
            />
          </div>

          {/* Platelets */}
          <div className="space-y-1">
            <Label htmlFor="plt">
              Platelets (/µL)
              {plt && !isNaN(parseInt(plt)) && (
                <span className="ml-1 text-xs text-muted-foreground">
                  = {(parseInt(plt) / 100000).toFixed(2)} lakh
                </span>
              )}
            </Label>
            <Input id="plt" type="number" step="1000" min="5000" max="1500000"
              value={plt} onChange={e => setPlt(e.target.value)}
              placeholder="e.g. 150000"
              className={!plt ? 'border-yellow-400' : ''}
            />
          </div>

          {/* BP Systolic */}
          <div className="space-y-1">
            <Label htmlFor="bpSys">BP Systolic (mmHg)</Label>
            <Input id="bpSys" type="number" min="70" max="220"
              value={bpSys} onChange={e => setBpSys(e.target.value)}
              placeholder="e.g. 120"
              className={!bpSys ? 'border-yellow-400' : ''}
            />
          </div>

          {/* BP Diastolic */}
          <div className="space-y-1">
            <Label htmlFor="bpDia">BP Diastolic (mmHg)</Label>
            <Input id="bpDia" type="number" min="40" max="140"
              value={bpDia} onChange={e => setBpDia(e.target.value)}
              placeholder="e.g. 80"
              className={!bpDia ? 'border-yellow-400' : ''}
            />
          </div>

          {/* Gestational Age */}
          <div className="space-y-1">
            <Label htmlFor="ga">
              Gestational Age (weeks)
              <span className="ml-1 text-xs text-muted-foreground">= months of pregnancy</span>
            </Label>
            <Input id="ga" type="number" min="4" max="42"
              value={ga} onChange={e => setGa(e.target.value)}
              placeholder="e.g. 28 (7 months)"
              className={!ga ? 'border-yellow-400' : ''}
            />
            {ga && !isNaN(parseInt(ga)) && (
              <p className="text-xs text-muted-foreground">
                ≈ {(parseInt(ga) / 4.33).toFixed(1)} months
              </p>
            )}
          </div>

          {/* Proteinuria */}
          <div className="space-y-1">
            <Label>Proteinuria (urine test)</Label>
            <Select value={proto} onValueChange={setProto}>
              <SelectTrigger>
                <SelectValue placeholder="Select result" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="nil">Nil (negative)</SelectItem>
                <SelectItem value="+1">+1 (trace)</SelectItem>
                <SelectItem value="+2">+2 (moderate)</SelectItem>
                <SelectItem value="+3">+3 (severe)</SelectItem>
              </SelectContent>
            </Select>
          </div>

        </div>

        {/* Missing values warning */}
        {(!hb || !plt || !bpSys || !bpDia) && (
          <p className="text-xs text-yellow-700 bg-yellow-50 rounded p-2">
            ⚠️ Fields with yellow border were not found in the image.
            Fill them in manually for an accurate assessment.
          </p>
        )}

        <DialogFooter className="gap-2 pt-2">
          <Button variant="outline" onClick={onCancel} disabled={isLoading}>
            Cancel
          </Button>
          <Button
            onClick={handleConfirm}
            disabled={isLoading}
            variant={hasCritical ? 'destructive' : 'default'}
            className="min-w-[140px]"
          >
            {isLoading ? 'Running assessment…' : 'Confirm & Assess'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
