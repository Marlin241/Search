"use client";

export interface SalarySliderProps {
  min: number;
  max: number;
  step: number;
  valueMin: number;
  valueMax: number;
  onChange: (min: number, max: number) => void;
}

export function SalarySlider({
  min,
  max,
  step,
  valueMin,
  valueMax,
  onChange,
}: SalarySliderProps) {
  return (
    <div className="space-y-3">
      <label className="block text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        Fourchette de salaire souhaitée (€ brut / an)
      </label>

      <div className="relative h-1.5 rounded-full bg-muted">
        <div
          className="absolute h-1.5 rounded-full bg-primary"
          style={{
            left: `${((valueMin - min) / (max - min)) * 100}%`,
            right: `${100 - ((valueMax - min) / (max - min)) * 100}%`,
          }}
        />
        <input
          type="range"
          min={min}
          max={max}
          step={step}
          value={valueMin}
          onChange={(e) => {
            const next = Math.min(Number(e.target.value), valueMax - step);
            onChange(next, valueMax);
          }}
          className="pointer-events-none absolute inset-0 h-1.5 w-full appearance-none bg-transparent [&::-webkit-slider-thumb]:pointer-events-auto [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-primary [&::-webkit-slider-thumb]:shadow-soft"
        />
        <input
          type="range"
          min={min}
          max={max}
          step={step}
          value={valueMax}
          onChange={(e) => {
            const next = Math.max(Number(e.target.value), valueMin + step);
            onChange(valueMin, next);
          }}
          className="pointer-events-none absolute inset-0 h-1.5 w-full appearance-none bg-transparent [&::-webkit-slider-thumb]:pointer-events-auto [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-primary [&::-webkit-slider-thumb]:shadow-soft"
        />
      </div>

      <div className="flex items-center gap-3">
        <div className="flex-1">
          <input
            type="number"
            min={min}
            max={valueMax - step}
            step={step}
            value={valueMin}
            onChange={(e) =>
              onChange(
                Math.min(Number(e.target.value), valueMax - step),
                valueMax
              )
            }
            className="w-full rounded-xl border border-input bg-card px-3 py-2 text-sm text-foreground outline-none focus:ring-2 focus:ring-ring"
          />
        </div>
        <span className="text-xs text-muted-foreground">à</span>
        <div className="flex-1">
          <input
            type="number"
            min={valueMin + step}
            max={max}
            step={step}
            value={valueMax}
            onChange={(e) =>
              onChange(
                valueMin,
                Math.max(Number(e.target.value), valueMin + step)
              )
            }
            className="w-full rounded-xl border border-input bg-card px-3 py-2 text-sm text-foreground outline-none focus:ring-2 focus:ring-ring"
          />
        </div>
      </div>
    </div>
  );
}
