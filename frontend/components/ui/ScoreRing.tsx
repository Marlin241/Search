"use client";

import React, { useEffect, useState } from "react";
import { cn, scoreColor, scoreGradientId } from "@/lib/utils";

export interface ScoreRingProps {
  score: number;
  size?: "sm" | "md" | "lg" | number;
  label?: string;
  className?: string;
}

export const ScoreRing: React.FC<ScoreRingProps> = ({
  score,
  size = "md",
  label,
  className,
}) => {
  const [animatedScore, setAnimatedScore] = useState(0);

  useEffect(() => {
    const timer = setTimeout(() => {
      setAnimatedScore(Math.min(100, Math.max(0, score)));
    }, 80);
    return () => clearTimeout(timer);
  }, [score]);

  const presetSizes = {
    sm: { dimension: 44, stroke: 4, text: "text-xs font-bold" },
    md: { dimension: 80, stroke: 6, text: "text-xl font-bold font-display" },
    lg: { dimension: 130, stroke: 9, text: "text-3xl font-extrabold font-display" },
  };

  const config =
    typeof size === "number"
      ? { dimension: size, stroke: Math.max(3, size / 10), text: "text-sm font-bold font-display" }
      : presetSizes[size];

  const radius = (config.dimension - config.stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (animatedScore / 100) * circumference;

  return (
    <div className={cn("inline-flex flex-col items-center justify-center gap-1", className)}>
      <div
        className="relative inline-flex items-center justify-center"
        style={{ width: config.dimension, height: config.dimension }}
      >
        <svg
          className="h-full w-full -rotate-90 transform"
          viewBox={`0 0 ${config.dimension} ${config.dimension}`}
        >
          {/* Background track */}
          <circle
            className="text-muted/40"
            strokeWidth={config.stroke}
            stroke="currentColor"
            fill="transparent"
            r={radius}
            cx={config.dimension / 2}
            cy={config.dimension / 2}
          />
          {/* Animated fill circle */}
          <circle
            stroke={`url(#${scoreGradientId(score)})`}
            strokeWidth={config.stroke}
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
            strokeLinecap="round"
            fill="transparent"
            r={radius}
            cx={config.dimension / 2}
            cy={config.dimension / 2}
            style={{
              transition: "stroke-dashoffset 1.2s cubic-bezier(0.16, 1, 0.3, 1)",
            }}
          />
        </svg>

        {/* Center label */}
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className={cn(config.text, scoreColor(score))}>
            {animatedScore}
            <span className="text-[0.65em] font-normal opacity-80">%</span>
          </span>
        </div>
      </div>

      {label && (
        <span className="text-center text-xs font-medium text-muted-foreground">
          {label}
        </span>
      )}
    </div>
  );
};
