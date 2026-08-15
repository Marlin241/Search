"use client";

import { useRef, useState, type DragEvent, type ChangeEvent } from "react";
import { Upload } from "lucide-react";
import { validateCvFile } from "@/lib/validation";

interface CVDropzoneProps {
  file: File | null;
  onFileSelected: (file: File | null) => void;
}

export function CVDropzone({ file, onFileSelected }: CVDropzoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [error, setError] = useState<string | null>(null);

  function handleFile(candidate: File | undefined) {
    if (!candidate) return;
    const validationError = validateCvFile(candidate);
    setError(validationError);
    onFileSelected(validationError ? null : candidate);
  }

  function handleInputChange(event: ChangeEvent<HTMLInputElement>) {
    handleFile(event.target.files?.[0]);
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    handleFile(event.dataTransfer.files?.[0]);
  }

  return (
    <div>
      <div
        onClick={() => inputRef.current?.click()}
        onDragOver={(event) => event.preventDefault()}
        onDrop={handleDrop}
        className="cursor-pointer rounded-[22px] border-2 border-dashed border-border-strong bg-surface p-7 text-center transition-colors hover:border-accent"
      >
        <Upload className="mx-auto h-6 w-6 text-accent-strong" aria-hidden="true" />
        <p className="mt-2.5 text-sm font-bold text-ink">
          {file ? file.name : "Glissez votre CV ici ou cliquez pour parcourir"}
        </p>
        <p className="mt-1 text-xs text-ink-faint">PDF ou DOCX, 5 Mo max</p>
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.docx"
          onChange={handleInputChange}
          className="sr-only"
          aria-label="Sélectionner un CV"
        />
      </div>
      {error && (
        <p role="alert" className="mt-2 text-sm font-medium text-attention-ink">
          {error}
        </p>
      )}
    </div>
  );
}
