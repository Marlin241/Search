"use client";

import { useId } from "react";

interface ScoreCircleProps {
  score: number;
  size?: "lg" | "sm";
  label?: string;
}

const SIZES = {
  lg: { diameter: 160, stroke: 14, fontSize: "text-[42px]" },
  sm: { diameter: 52, stroke: 6, fontSize: "text-base" },
} as const;

export function ScoreCircle({ score, size = "lg", label }: ScoreCircleProps) {
  const gradientId = useId();
  const clamped = Math.min(100, Math.max(0, score));
  const { diameter, stroke, fontSize } = SIZES[size];
  const radius = (diameter - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - clamped / 100);

  return (
    <div className="flex flex-col items-center gap-1">
      <div className="relative" style={{ width: diameter, height: diameter }}>
        <svg width={diameter} height={diameter} viewBox={`0 0 ${diameter} ${diameter}`}>
          <defs>
            <linearGradient id={gradientId} x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stopColor="var(--accent)" />
              <stop offset="100%" stopColor="var(--accent-strong)" />
            </linearGradient>
          </defs>
          <circle cx={diameter / 2} cy={diameter / 2} r={radius} fill="none" className="stroke-surface-2" strokeWidth={stroke} />
          <circle
            cx={diameter / 2}
            cy={diameter / 2}
            r={radius}
            fill="none"
            stroke={`url(#${gradientId})`}
            strokeWidth={stroke}
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            strokeLinecap="round"
            transform={`rotate(-90 ${diameter / 2} ${diameter / 2})`}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className={`font-display ${fontSize} font-extrabold leading-none text-ink`}>{clamped}</span>
          {size === "lg" && <span className="text-xs font-bold text-ink-faint">/ 100</span>}
        </div>
      </div>
      {label && <span className="text-xs text-ink-soft">{label}</span>}
    </div>
  );
}
