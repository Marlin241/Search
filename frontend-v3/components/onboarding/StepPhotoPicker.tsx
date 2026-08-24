"use client";

import { useEffect, useRef, useState } from "react";
import { Check, ImageIcon, Upload, User } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { getProfilePhoto } from "@/lib/api";
import { getInitials, cn } from "@/lib/utils";
import type { ExtractedPhotoOut } from "@/lib/types";

function AuthenticatedThumb({ preview_url }: { preview_url: string }) {
  const { token } = useAuth();
  const [src, setSrc] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    let objectUrl: string | null = null;
    getProfilePhoto(token, preview_url)
      .then((blob) => {
        objectUrl = URL.createObjectURL(blob);
        setSrc(objectUrl);
      })
      .catch(() => setSrc(null));
    return () => {
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [token, preview_url]);

  if (!src) {
    return <div className="h-full w-full animate-pulse bg-muted" />;
  }
  // eslint-disable-next-line @next/next/no-img-element
  return <img src={src} alt="" className="h-full w-full object-cover" />;
}

export interface StepPhotoPickerProps {
  candidates: ExtractedPhotoOut[];
  isExtracting: boolean;
  selectedKey: string | null;
  onSelect: (key: string | null) => void;
  fullName: string;
  onManualUpload: (file: File) => void;
}

export function StepPhotoPicker({
  candidates,
  isExtracting,
  selectedKey,
  onSelect,
  fullName,
  onManualUpload,
}: StepPhotoPickerProps) {
  const inputRef = useRef<HTMLInputElement>(null);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="font-display text-2xl font-bold text-foreground">
          Photo de profil
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">
          {isExtracting
            ? "On regarde si ton CV contient une photo..."
            : candidates.length > 0
              ? `${candidates.length} image${candidates.length > 1 ? "s" : ""} détectée${candidates.length > 1 ? "s" : ""} dans ton CV.`
              : "Aucune image détectée dans ton CV — pas de souci, tu peux en choisir une autre ou garder ton avatar par défaut."}
        </p>
      </div>

      <div className="grid grid-cols-3 gap-3 sm:grid-cols-4">
        {/* Default initials avatar */}
        <button
          type="button"
          onClick={() => onSelect(null)}
          className={cn(
            "flex aspect-square flex-col items-center justify-center gap-1 rounded-2xl border-2 transition-all",
            selectedKey === null
              ? "border-primary ring-2 ring-primary/30"
              : "border-border hover:border-primary/40"
          )}
        >
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary/15 font-display text-sm font-bold text-primary">
            {fullName ? getInitials(fullName) : <User className="h-5 w-5" />}
          </div>
          <span className="text-[10px] font-medium text-muted-foreground">
            Par défaut
          </span>
        </button>

        {isExtracting &&
          Array.from({ length: 2 }).map((_, i) => (
            <div
              key={`skeleton-${i}`}
              className="aspect-square animate-pulse rounded-2xl bg-muted"
            />
          ))}

        {candidates.map((candidate) => {
          const selected = selectedKey === candidate.key;
          return (
            <button
              key={candidate.key}
              type="button"
              onClick={() => onSelect(candidate.key)}
              className={cn(
                "relative aspect-square overflow-hidden rounded-2xl border-2 transition-all",
                selected
                  ? "border-primary ring-2 ring-primary/30"
                  : "border-border hover:border-primary/40"
              )}
            >
              <AuthenticatedThumb preview_url={candidate.preview_url} />
              {selected && (
                <span className="absolute right-1.5 top-1.5 flex h-5 w-5 items-center justify-center rounded-full bg-primary text-white">
                  <Check className="h-3 w-3" />
                </span>
              )}
            </button>
          );
        })}

        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          className="flex aspect-square flex-col items-center justify-center gap-1 rounded-2xl border-2 border-dashed border-border text-muted-foreground transition-colors hover:border-primary/40 hover:text-primary"
        >
          {candidates.length > 0 ? (
            <ImageIcon className="h-5 w-5" />
          ) : (
            <Upload className="h-5 w-5" />
          )}
          <span className="text-[10px] font-medium">
            Importer une image
          </span>
          <input
            ref={inputRef}
            type="file"
            accept="image/*"
            className="hidden"
            onChange={(e) => {
              if (e.target.files?.[0]) onManualUpload(e.target.files[0]);
            }}
          />
        </button>
      </div>
    </div>
  );
}
