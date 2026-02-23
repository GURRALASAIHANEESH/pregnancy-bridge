"use client"

import { useState, useMemo } from "react"
import { useLanguage } from "./language-provider"
import { RiskBadge } from "./risk-badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Plus, Search, Eye, Users } from "lucide-react"
import type { Patient, Visit } from "@/lib/types"
import { format } from "date-fns"

interface PatientListProps {
  patients: (Patient & { latestVisit?: Visit })[]
  onNewPatient: () => void
  onViewPatient: (id: string) => void
}

export function PatientList({ patients, onNewPatient, onViewPatient }: PatientListProps) {
  const { t } = useLanguage()
  const [search, setSearch] = useState("")

  const filtered = useMemo(() => {
    if (!search.trim()) return patients
    const q = search.toLowerCase()
    return patients.filter(
      (p) =>
        p.name.toLowerCase().includes(q) ||
        p.village.toLowerCase().includes(q) ||
        p.phone.includes(q)
    )
  }, [patients, search])

  return (
    <div className="space-y-4">
      {/* Actions bar */}
      <div className="flex flex-col sm:flex-row gap-3 items-start sm:items-center justify-between">
        <div className="flex items-center gap-2">
          <Users className="h-5 w-5 text-primary" />
          <h2 className="text-xl font-bold text-foreground">{t("patients")}</h2>
          <span className="text-sm text-muted-foreground">
            {"("}{patients.length}{")"}
          </span>
        </div>
        <div className="flex gap-3 w-full sm:w-auto">
          <div className="relative flex-1 sm:flex-initial">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder={t("searchPatients")}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9 bg-card w-full sm:w-64"
            />
          </div>
          <Button onClick={onNewPatient} className="bg-primary text-primary-foreground hover:bg-primary/90 flex-shrink-0">
            <Plus className="h-4 w-4 mr-1.5" />
            {t("newPatient")}
          </Button>
        </div>
      </div>

      {/* Patient table */}
      <Card className="shadow-sm border-border">
        <CardContent className="p-0">
          {filtered.length === 0 ? (
            <div className="py-16 text-center">
              <Users className="h-12 w-12 text-muted-foreground/40 mx-auto mb-3" />
              <p className="text-muted-foreground">{t("noPatients")}</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow className="bg-muted/50">
                    <TableHead className="text-foreground font-semibold">{t("name")}</TableHead>
                    <TableHead className="text-foreground font-semibold">{t("age")}</TableHead>
                    <TableHead className="text-foreground font-semibold hidden sm:table-cell">{t("village")}</TableHead>
                    <TableHead className="text-foreground font-semibold">{t("riskLevel")}</TableHead>
                    <TableHead className="text-foreground font-semibold hidden md:table-cell">{t("lastVisit")}</TableHead>
                    <TableHead className="text-foreground font-semibold text-right">{t("actions")}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filtered.map((patient) => (
                    <TableRow
                      key={patient.id}
                      className="hover:bg-accent/50 cursor-pointer"
                      onClick={() => onViewPatient(patient.id)}
                    >
                      <TableCell className="font-medium text-foreground">
                        <div>
                          <p className="font-medium">{patient.name}</p>
                          <p className="text-xs text-muted-foreground sm:hidden">{patient.village}</p>
                        </div>
                      </TableCell>
                      <TableCell className="text-foreground">{patient.age}</TableCell>
                      <TableCell className="text-foreground hidden sm:table-cell">{patient.village}</TableCell>
                      <TableCell>
                        {patient.latestVisit?.result ? (
                          <RiskBadge level={patient.latestVisit.result.risk_level} size="sm" />
                        ) : (
                          <span className="text-xs text-muted-foreground">{"--"}</span>
                        )}
                      </TableCell>
                      <TableCell className="text-foreground hidden md:table-cell">
                        {patient.latestVisit ? (
                          format(new Date(patient.latestVisit.date), "dd MMM yyyy")
                        ) : (
                          <span className="text-muted-foreground">{"--"}</span>
                        )}
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={(e) => {
                            e.stopPropagation()
                            onViewPatient(patient.id)
                          }}
                          className="text-primary hover:text-primary hover:bg-accent"
                        >
                          <Eye className="h-4 w-4 mr-1" />
                          <span className="hidden sm:inline">{t("viewDetails")}</span>
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
