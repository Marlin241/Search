"use client";

import { useRef, useState, type DragEvent, type ChangeEvent } from "react";
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
        className="cursor-pointer rounded-xl border-2 border-dashed border-blue-200 bg-white p-7 text-center"
      >
        <p className="text-sm font-semibold text-slate-900">
          {file ? file.name : "Glissez votre CV ici ou cliquez pour parcourir"}
        </p>
        <p className="mt-1 text-xs text-slate-500">PDF ou DOCX, 5 Mo max</p>
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.docx"
          onChange={handleInputChange}
          className="hidden"
          aria-label="Sélectionner un CV"
        />
      </div>
      {error && (
        <p role="alert" className="mt-2 text-sm text-red-600">
          {error}
        </p>
      )}
    </div>
  );
}
