import { cn } from "@/lib/utils";

export function ProgressDots({
  total,
  current,
}: {
  total: number;
  current: number;
}) {
  return (
    <div className="space-y-2">
      <p className="text-xs font-semibold uppercase tracking-widest text-white/70">
        Étape {current + 1} sur {total}
      </p>
      <div className="flex gap-1.5">
        {Array.from({ length: total }).map((_, i) => (
          <div
            key={i}
            className={cn(
              "h-1.5 rounded-full transition-all",
              i === current
                ? "w-8 bg-white"
                : i < current
                  ? "w-4 bg-white/70"
                  : "w-4 bg-white/25"
            )}
          />
        ))}
      </div>
    </div>
  );
}
