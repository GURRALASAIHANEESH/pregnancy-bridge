import React from "react"
import type { Metadata, Viewport } from "next"
import { Noto_Sans } from "next/font/google"

import "./globals.css"

const notoSans = Noto_Sans({
  subsets: ["latin", "devanagari", "telugu"],
  variable: "--font-noto-sans",
  weight: ["400", "500", "600", "700"],
  display: "swap",
})

export const metadata: Metadata = {
  title: "Pregnancy Risk Assessment | NHM Field Tool",
  description:
    "AI-powered pregnancy risk assessment tool for National Health Mission field workers. Supports English, Telugu, and Hindi.",
}

export const viewport: Viewport = {
  themeColor: "#1565C0",
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en" className={notoSans.variable}>
      <body className="font-sans antialiased min-h-screen bg-background text-foreground">
        {children}
      </body>
    </html>
  )
}
