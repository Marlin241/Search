"use client";

import { useRef, useState } from "react";
import { CheckCircle2, Upload, X } from "lucide-react";
import { isValidCvFile, MAX_FILE_SIZE, cn } from "@/lib/utils";

export interface StepGoalsAndCvProps {
  weeklyGoal: number;
  onWeeklyGoalChange: (value: number) => void;
  cvFile: File | null;
  onCvFileSelected: (file: File) => void;
  onCvFileCleared: () => void;
}

export function StepGoalsAndCv({
  weeklyGoal,
  onWeeklyGoalChange,
  cvFile,
  onCvFileSelected,
  onCvFileCleared,
}: StepGoalsAndCvProps) {
  const [fileError, setFileError] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const validateAndSet = (file: File) => {
    if (!isValidCvFile(file)) {
      setFileError("Format non supporté. Choisis un fichier PDF ou DOCX.");
      return;
    }
    if (file.size > MAX_FILE_SIZE) {
      setFileError("Le fichier est trop volumineux (maximum 5 Mo).");
      return;
    }
    setFileError(null);
    onCvFileSelected(file);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files?.[0]) validateAndSet(e.dataTransfer.files[0]);
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="font-display text-2xl font-bold text-foreground">
          Ton rythme et ton CV
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Définis ton objectif de candidatures et importe ton CV de
          référence.
        </p>
      </div>

      <div className="space-y-3">
        <label className="block text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Objectif de candidatures par semaine
        </label>
        <div className="flex items-center gap-4">
          <input
            type="range"
            min={1}
            max={50}
            value={weeklyGoal}
            onChange={(e) => onWeeklyGoalChange(Number(e.target.value))}
            className="h-1.5 flex-1 cursor-pointer appearance-none rounded-full bg-muted accent-primary [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-primary"
          />
          <span className="w-16 shrink-0 rounded-lg bg-primary/10 py-1.5 text-center font-display text-sm font-bold text-primary">
            {weeklyGoal}/sem.
          </span>
        </div>
      </div>

      <div className="space-y-2">
        <label className="block text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          CV de référence
        </label>

        {!cvFile ? (
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setIsDragging(true);
            }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={handleDrop}
            onClick={() => inputRef.current?.click()}
            className={cn(
              "flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed px-6 py-10 text-center transition-colors",
              isDragging
                ? "border-primary bg-primary/5"
                : "border-border hover:border-primary/40"
            )}
          >
            <Upload className="h-6 w-6 text-muted-foreground" />
            <p className="text-sm font-semibold text-foreground">
              Téléverser mon CV de référence
            </p>
            <p className="text-xs text-muted-foreground">
              Format PDF ou DOCX (max 5 Mo)
            </p>
            <input
              ref={inputRef}
              type="file"
              accept=".pdf,.docx"
              className="hidden"
              onChange={(e) => {
                if (e.target.files?.[0]) validateAndSet(e.target.files[0]);
              }}
            />
          </div>
        ) : (
          <div className="flex items-center justify-between rounded-xl border border-success/30 bg-success/5 px-4 py-3">
            <div className="flex items-center gap-2.5">
              <CheckCircle2 className="h-5 w-5 shrink-0 text-success" />
              <div>
                <p className="text-sm font-semibold text-foreground">
                  Fichier prêt
                </p>
                <p className="text-xs text-muted-foreground">{cvFile.name}</p>
              </div>
            </div>
            <button
              type="button"
              onClick={onCvFileCleared}
              className="rounded-full p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground"
              aria-label="Retirer le fichier"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        )}

        {fileError && <p className="text-xs text-destructive">{fileError}</p>}

        <p className="text-xs text-muted-foreground">
          Ce CV sera ta base de référence. Tu pourras l'optimiser pour chaque
          offre depuis la page de l'offre.
        </p>
      </div>
    </div>
  );
}
