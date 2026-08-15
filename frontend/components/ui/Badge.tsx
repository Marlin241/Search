import type { HTMLAttributes } from "react";

export type BadgeVariant = "neutral" | "accent" | "success" | "pending" | "attention";

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
}

const VARIANT_CLASSES: Record<BadgeVariant, string> = {
  neutral: "bg-surface-2 text-ink-soft",
  accent: "bg-accent-soft text-accent-ink",
  success: "bg-success-soft text-success-ink",
  pending: "bg-pending-soft text-pending-ink",
  attention: "bg-attention-soft text-attention-ink",
};

export function Badge({ variant = "neutral", className = "", ...props }: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-bold ${VARIANT_CLASSES[variant]} ${className}`}
      {...props}
    />
  );
}
