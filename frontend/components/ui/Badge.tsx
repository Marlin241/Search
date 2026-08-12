import type { HTMLAttributes } from "react";

export type BadgeVariant = "neutral" | "amber" | "emerald" | "red";

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
}

const VARIANT_CLASSES: Record<BadgeVariant, string> = {
  neutral: "bg-slate-100 text-slate-700 dark:bg-ink-800 dark:text-slate-300",
  amber: "bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-400",
  emerald: "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-400",
  red: "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-400",
};

export function Badge({ variant = "neutral", className = "", ...props }: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold ${VARIANT_CLASSES[variant]} ${className}`}
      {...props}
    />
  );
}
