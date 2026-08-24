import { Sparkles } from "lucide-react";
import { cn, scoreColor } from "@/lib/utils";

export interface CompatibilityBadgeProps {
  score: number;
  className?: string;
}

const BACKGROUND_BY_TIER = (score: number): string => {
  if (score >= 70) return "bg-success/15 border-success/30";
  if (score >= 40) return "bg-warning/15 border-warning/30";
  return "bg-destructive/15 border-destructive/30";
};

export function CompatibilityBadge({ score, className }: CompatibilityBadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs font-bold",
        BACKGROUND_BY_TIER(score),
        scoreColor(score),
        className
      )}
      title="Score de compatibilité avec votre profil"
    >
      <Sparkles className="h-3 w-3" aria-hidden="true" />
      {score}% compatible
    </span>
  );
}
