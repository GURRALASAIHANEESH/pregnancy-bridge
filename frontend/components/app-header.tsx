"use client"

import { useLanguage } from "./language-provider"
import type { Language } from "@/lib/translations"
import { Globe } from "lucide-react"

const languageLabels: Record<Language, string> = {
  en: "EN",
  te: "తె",
  hi: "हि",
}

const languageNames: Record<Language, string> = {
  en: "English",
  te: "తెలుగు",
  hi: "हिंदी",
}

export function AppHeader() {
  const { lang, setLang, t } = useLanguage()

  return (
    <header className="bg-primary text-primary-foreground shadow-md">
      {/* Top bar - Government style */}
      <div className="bg-primary/90 border-b border-primary-foreground/15">
        <div className="max-w-7xl mx-auto px-4 py-1.5 flex items-center justify-between">
          <p className="text-xs text-primary-foreground/80 hidden sm:block">
            {"Government of India | National Health Mission"}
          </p>
          <div className="flex items-center gap-1 ml-auto">
            <Globe className="h-3.5 w-3.5 text-primary-foreground/70" />
            {(["en", "te", "hi"] as Language[]).map((l) => (
              <button
                key={l}
                onClick={() => setLang(l)}
                className={`px-2 py-0.5 text-xs rounded transition-colors ${
                  lang === l
                    ? "bg-primary-foreground text-primary font-semibold"
                    : "text-primary-foreground/80 hover:bg-primary-foreground/15"
                }`}
                aria-label={`Switch to ${languageNames[l]}`}
                title={languageNames[l]}
              >
                {languageLabels[l]}
              </button>
            ))}
          </div>
        </div>
      </div>
      {/* Main header */}
      <div className="max-w-7xl mx-auto px-4 py-3">
        <div className="flex items-center gap-3">
          <div className="flex items-center justify-center h-10 w-10 rounded-full bg-primary-foreground/15 flex-shrink-0">
            <svg
              className="h-6 w-6 text-primary-foreground"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={1.5}
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M21 8.25c0-2.485-2.099-4.5-4.688-4.5-1.935 0-3.597 1.126-4.312 2.733-.715-1.607-2.377-2.733-4.313-2.733C5.1 3.75 3 5.765 3 8.25c0 7.22 9 12 9 12s9-4.78 9-12z"
              />
            </svg>
          </div>
          <div className="min-w-0">
            <h1 className="text-lg font-bold leading-tight text-primary-foreground text-balance">
              {t("appTitle")}
            </h1>
            <p className="text-xs text-primary-foreground/75 mt-0.5 leading-tight">
              {t("appSubtitle")}
            </p>
          </div>
        </div>
      </div>
    </header>
  )
}
