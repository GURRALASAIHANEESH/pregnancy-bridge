"use client"

import React from "react"

import { useState, useCallback, useRef, type DragEvent } from "react"
import { useLanguage } from "./language-provider"
import { Upload, X } from "lucide-react"

interface ImageUploadProps {
  images: string[]
  onImagesChange: (images: string[]) => void
  maxImages?: number
}

export function ImageUpload({
  images,
  onImagesChange,
  maxImages = 5,
}: ImageUploadProps) {
  const { t } = useLanguage()
  const [isDragging, setIsDragging] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const processFiles = useCallback(
    (files: FileList | File[]) => {
      const remaining = maxImages - images.length
      if (remaining <= 0) return

      const fileArray = Array.from(files).slice(0, remaining)
      const validFiles = fileArray.filter((f) =>
        ["image/jpeg", "image/jpg", "image/png"].includes(f.type)
      )

      for (const file of validFiles) {
        const reader = new FileReader()
        reader.onload = (e) => {
          const base64 = e.target?.result as string
          onImagesChange([...images, base64])
        }
        reader.readAsDataURL(file)
      }
    },
    [images, maxImages, onImagesChange]
  )

  const handleDrop = useCallback(
    (e: DragEvent<HTMLButtonElement>) => {
      e.preventDefault()
      setIsDragging(false)
      processFiles(e.dataTransfer.files)
    },
    [processFiles]
  )

  const handleDragOver = useCallback((e: DragEvent<HTMLButtonElement>) => {
    e.preventDefault()
    setIsDragging(true)
  }, [])

  const handleDragLeave = useCallback((e: DragEvent<HTMLButtonElement>) => {
    e.preventDefault()
    setIsDragging(false)
  }, [])

  const removeImage = useCallback(
    (index: number) => {
      onImagesChange(images.filter((_, i) => i !== index))
    },
    [images, onImagesChange]
  )

  return (
    <div className="space-y-3">
      {/* Drop zone */}
      <button
        type="button"
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onClick={() => fileInputRef.current?.click()}
        className={`w-full border-2 border-dashed rounded-md p-6 text-center transition-colors cursor-pointer ${
          isDragging
            ? "border-primary bg-accent"
            : "border-border bg-card hover:border-primary/50 hover:bg-accent/50"
        } ${images.length >= maxImages ? "opacity-50 cursor-not-allowed" : ""}`}
        disabled={images.length >= maxImages}
      >
        <Upload className="h-8 w-8 mx-auto mb-2 text-muted-foreground" />
        <p className="text-sm text-foreground font-medium">{t("dragDrop")}</p>
        <p className="text-xs text-muted-foreground mt-1">{t("supportedFormats")}</p>
      </button>

      <input
        ref={fileInputRef}
        type="file"
        accept="image/jpeg,image/jpg,image/png"
        multiple
        onChange={(e) => {
          if (e.target.files) processFiles(e.target.files)
          e.target.value = ""
        }}
        className="sr-only"
        aria-label={t("uploadLabReports")}
      />

      {/* Image previews */}
      {images.length > 0 && (
        <div className="grid grid-cols-3 sm:grid-cols-5 gap-2">
          {images.map((img, index) => (
            <div
              key={`img-${index}`}
              className="relative group aspect-square rounded-md overflow-hidden border border-border bg-muted"
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={img || "/placeholder.svg"}
                alt={`Lab report ${index + 1}`}
                className="w-full h-full object-cover"
              />
              <button
                type="button"
                onClick={() => removeImage(index)}
                className="absolute top-1 right-1 h-5 w-5 rounded-full bg-destructive text-destructive-foreground flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
                aria-label={`Remove image ${index + 1}`}
              >
                <X className="h-3 w-3" />
              </button>
            </div>
          ))}
        </div>
      )}

      <p className="text-xs text-muted-foreground">
        {images.length} / {maxImages} {t("images")}
      </p>
    </div>
  )
}
