"use client";

import { Star } from "lucide-react";
import { cn } from "@/lib/utils";

export function QualityRatingStars({
  value,
  onChange,
}: {
  value: number;
  onChange: (value: number) => void;
}) {
  return (
    <div className="flex items-center gap-1">
      {[1, 2, 3, 4, 5].map((star) => (
        <button
          key={star}
          type="button"
          onClick={() => onChange(star)}
          aria-label={`${star} étoile${star > 1 ? "s" : ""}`}
          className="p-0.5 transition-transform hover:scale-110"
        >
          <Star
            className={cn(
              "w-4 h-4",
              star <= value
                ? "fill-warning text-warning"
                : "text-muted-foreground"
            )}
          />
        </button>
      ))}
    </div>
  );
}
