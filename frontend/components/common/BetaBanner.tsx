"use client";

import { useEffect, useState } from "react";
import { X } from "lucide-react";

const KEY = "beta_banner_dismissed";

export function BetaBanner() {
  const [hidden, setHidden] = useState(true);

  useEffect(() => {
    try {
      setHidden(localStorage.getItem(KEY) === "1");
    } catch {
      setHidden(false);
    }
  }, []);

  if (hidden) return null;

  return (
    <div className="flex items-center justify-between gap-3 bg-primary-600 px-4 py-2 text-xs text-white">
      <span>
        Version beta — certaines parties sont encore brutes. Un souci, une idée ?
        Utilise le bouton « Donner mon avis » ou le groupe WhatsApp.
      </span>
      <button
        aria-label="Fermer"
        className="shrink-0 rounded p-0.5 hover:bg-white/20"
        onClick={() => {
          try {
            localStorage.setItem(KEY, "1");
          } catch {
            /* storage unavailable */
          }
          setHidden(true);
        }}
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}
