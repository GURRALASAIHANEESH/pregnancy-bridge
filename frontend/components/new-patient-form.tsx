"use client"

import React from "react"

import { useState } from "react"
import { useLanguage } from "./language-provider"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { ArrowLeft, UserPlus } from "lucide-react"

interface NewPatientFormProps {
  onSave: (data: {
    name: string
    age: number
    phone: string
    village: string
    lmpDate: string
  }) => void
  onCancel: () => void
}

export function NewPatientForm({ onSave, onCancel }: NewPatientFormProps) {
  const { t } = useLanguage()
  const [name, setName] = useState("")
  const [age, setAge] = useState("")
  const [phone, setPhone] = useState("")
  const [village, setVillage] = useState("")
  const [lmpDate, setLmpDate] = useState("")
  const [errors, setErrors] = useState<Record<string, boolean>>({})

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const newErrors: Record<string, boolean> = {}

    if (!name.trim()) newErrors.name = true
    if (!age || Number(age) < 14 || Number(age) > 55) newErrors.age = true
    if (!phone.trim()) newErrors.phone = true
    if (!village.trim()) newErrors.village = true
    if (!lmpDate) newErrors.lmpDate = true

    setErrors(newErrors)
    if (Object.keys(newErrors).length > 0) return

    onSave({
      name: name.trim(),
      age: Number(age),
      phone: phone.trim(),
      village: village.trim(),
      lmpDate,
    })
  }

  return (
    <div className="space-y-4">
      <Button variant="ghost" onClick={onCancel} className="text-primary hover:text-primary hover:bg-accent gap-1.5">
        <ArrowLeft className="h-4 w-4" />
        {t("back")}
      </Button>

      <Card className="max-w-lg shadow-sm border-border">
        <CardHeader className="pb-4 border-b border-border bg-muted/30">
          <CardTitle className="flex items-center gap-2 text-foreground">
            <UserPlus className="h-5 w-5 text-primary" />
            {t("newPatient")}
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-6">
          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="space-y-2">
              <Label htmlFor="name" className="text-foreground font-medium">{t("name")}</Label>
              <Input
                id="name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className={`bg-card ${errors.name ? "border-destructive" : ""}`}
                placeholder="e.g. Lakshmi Devi"
              />
              {errors.name && (
                <p className="text-xs text-destructive">{t("requiredField")}</p>
              )}
            </div>

            <div className="flex gap-4">
              <div className="space-y-2 flex-1">
                <Label htmlFor="age" className="text-foreground font-medium">{t("age")}</Label>
                <Input
                  id="age"
                  type="number"
                  min={14}
                  max={55}
                  value={age}
                  onChange={(e) => setAge(e.target.value)}
                  className={`bg-card ${errors.age ? "border-destructive" : ""}`}
                  placeholder="e.g. 25"
                />
                {errors.age && (
                  <p className="text-xs text-destructive">{t("requiredField")}</p>
                )}
              </div>
              <div className="space-y-2 flex-1">
                <Label htmlFor="phone" className="text-foreground font-medium">{t("phone")}</Label>
                <Input
                  id="phone"
                  type="tel"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  className={`bg-card ${errors.phone ? "border-destructive" : ""}`}
                  placeholder="e.g. 9876543210"
                />
                {errors.phone && (
                  <p className="text-xs text-destructive">{t("requiredField")}</p>
                )}
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="village" className="text-foreground font-medium">{t("village")}</Label>
              <Input
                id="village"
                value={village}
                onChange={(e) => setVillage(e.target.value)}
                className={`bg-card ${errors.village ? "border-destructive" : ""}`}
                placeholder="e.g. Kondapur"
              />
              {errors.village && (
                <p className="text-xs text-destructive">{t("requiredField")}</p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="lmpDate" className="text-foreground font-medium">{t("lmpDate")}</Label>
              <Input
                id="lmpDate"
                type="date"
                value={lmpDate}
                onChange={(e) => setLmpDate(e.target.value)}
                className={`bg-card ${errors.lmpDate ? "border-destructive" : ""}`}
              />
              {errors.lmpDate && (
                <p className="text-xs text-destructive">{t("requiredField")}</p>
              )}
            </div>

            <div className="flex gap-3 pt-2">
              <Button
                type="submit"
                className="bg-primary text-primary-foreground hover:bg-primary/90 flex-1"
              >
                <UserPlus className="h-4 w-4 mr-1.5" />
                {t("addPatient")}
              </Button>
              <Button type="button" variant="outline" onClick={onCancel} className="border-border text-foreground hover:bg-muted bg-transparent">
                {t("cancel")}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
