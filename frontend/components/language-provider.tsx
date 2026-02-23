"use client"

import { createContext, useContext, useState, useCallback, type ReactNode } from "react"
import { type Language, t as translate } from "@/lib/translations"

interface LanguageContextType {
  lang: Language
  setLang: (lang: Language) => void
  t: (key: Parameters<typeof translate>[1]) => string
}

const LanguageContext = createContext<LanguageContextType | null>(null)

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Language>("en")

  const setLang = useCallback((newLang: Language) => {
    setLangState(newLang)
  }, [])

  const t = useCallback(
    (key: Parameters<typeof translate>[1]) => translate(lang, key),
    [lang]
  )

  return (
    <LanguageContext.Provider value={{ lang, setLang, t }}>
      {children}
    </LanguageContext.Provider>
  )
}

export function useLanguage() {
  const ctx = useContext(LanguageContext)
  if (!ctx) throw new Error("useLanguage must be used within LanguageProvider")
  return ctx
}
