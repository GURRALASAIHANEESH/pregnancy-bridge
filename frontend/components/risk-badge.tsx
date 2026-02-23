"use client"

import { useLanguage } from "./language-provider"
import { Badge } from "@/components/ui/badge"

interface RiskBadgeProps {
  level: "Low" | "Medium" | "High" | "Unknown" | string
  size?: "sm" | "md"
}

export function RiskBadge({ level, size = "md" }: RiskBadgeProps) {
  const { t } = useLanguage()

  const configs: Record<string, { label: string; className: string; dot: string }> = {
    Low: {
      label: t("low"),
      className: "bg-success text-success-foreground hover:bg-success/90",
      dot: "bg-success-foreground",
    },
    Medium: {
      label: t("medium"),
      className: "bg-warning text-warning-foreground hover:bg-warning/90",
      dot: "bg-warning-foreground",
    },
    High: {
      label: t("high"),
      className: "bg-destructive text-destructive-foreground hover:bg-destructive/90",
      dot: "bg-destructive-foreground",
    },
    Unknown: {
      label: "Unknown",
      className: "bg-muted text-muted-foreground hover:bg-muted/90",
      dot: "bg-muted-foreground",
    },
  }

  // Normalise backend uppercase values (HIGH/MODERATE/LOW) to Title-case keys
  const normalised = (level || '').charAt(0).toUpperCase() + (level || '').slice(1).toLowerCase()
  const resolvedKey =
    normalised === 'Moderate' ? 'Medium' :
      normalised === 'Unknown' ? 'Unknown' :
        normalised
  const { label, className, dot } = configs[resolvedKey] || configs['Unknown']

  return (
    <Badge
      className={`${className} ${size === "sm" ? "text-xs px-2 py-0.5" : "text-sm px-3 py-1"} gap-1.5 font-semibold`}
    >
      <span className={`inline-block h-2 w-2 rounded-full ${dot}`} aria-hidden="true" />
      {label}
    </Badge>
  )
}
