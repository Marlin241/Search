"use client";

import React, { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

export interface DialogProps {
  isOpen: boolean;
  onClose: () => void;
  title?: string;
  description?: string;
  children: React.ReactNode;
  className?: string;
}

const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

export const Dialog: React.FC<DialogProps> = ({
  isOpen,
  onClose,
  title,
  description,
  children,
  className,
}) => {
  const [mounted, setMounted] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const previouslyFocused = useRef<HTMLElement | null>(null);
  // Toujours à jour sans figurer dans les deps de l'effet ci-dessous : un
  // appelant qui passe `onClose={() => ...}` en inline (courant) recrée cette
  // fonction à chaque rendu. Si l'effet en dépendait, il se relancerait à
  // chaque frappe dans un champ du dialogue et redéplacerait le focus.
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => setMounted(true), []);

  useEffect(() => {
    if (!isOpen) return;

    previouslyFocused.current = document.activeElement as HTMLElement | null;
    document.body.style.overflow = "hidden";

    const focusFirst = () => {
      const node = containerRef.current;
      if (!node) return;
      const focusable = node.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR);
      (focusable[0] ?? node).focus();
    };
    focusFirst();

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onCloseRef.current();
        return;
      }
      if (e.key !== "Tab") return;

      const node = containerRef.current;
      if (!node) return;
      const focusable = Array.from(
        node.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)
      );
      if (focusable.length === 0) return;

      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      const active = document.activeElement;

      if (e.shiftKey && active === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && active === last) {
        e.preventDefault();
        first.focus();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      document.body.style.overflow = "unset";
      window.removeEventListener("keydown", handleKeyDown);
      previouslyFocused.current?.focus?.();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- onClose lu via onCloseRef, voir plus haut
  }, [isOpen]);

  if (!isOpen || !mounted) return null;

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="presentation"
    >
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-background/80 backdrop-blur-sm transition-opacity"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Modal Dialog Content */}
      <div
        ref={containerRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={title ? "dialog-title" : undefined}
        aria-describedby={description ? "dialog-description" : undefined}
        tabIndex={-1}
        className={cn(
          "relative z-50 flex max-h-[85vh] w-full max-w-lg flex-col rounded-2xl border border-border bg-card shadow-lift animate-scale-in outline-none",
          className
        )}
      >
        <button
          onClick={onClose}
          className="absolute right-4 top-4 rounded-full p-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          aria-label="Fermer"
        >
          <X className="h-4 w-4" />
        </button>

        {title && (
          <div className="shrink-0 px-6 pb-4 pt-6 pr-8">
            <h3 id="dialog-title" className="font-display text-lg font-bold text-foreground">
              {title}
            </h3>
            {description && (
              <p id="dialog-description" className="mt-1 text-sm text-muted-foreground">
                {description}
              </p>
            )}
          </div>
        )}

        <div className={cn("overflow-y-auto px-6 pb-6", !title && "pt-6")}>{children}</div>
      </div>
    </div>,
    document.body
  );
};
