interface ScoreCircleProps {
  score: number;
  size?: "lg" | "sm";
  label?: string;
}

const SIZES = {
  lg: { diameter: 96, stroke: 8, fontSize: "text-2xl" },
  sm: { diameter: 56, stroke: 6, fontSize: "text-base" },
} as const;

export function ScoreCircle({ score, size = "lg", label }: ScoreCircleProps) {
  const clamped = Math.min(100, Math.max(0, score));
  const { diameter, stroke, fontSize } = SIZES[size];
  const radius = (diameter - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - clamped / 100);

  return (
    <div className="flex flex-col items-center gap-1">
      <svg width={diameter} height={diameter} viewBox={`0 0 ${diameter} ${diameter}`}>
        <circle cx={diameter / 2} cy={diameter / 2} r={radius} fill="none" stroke="#dbeafe" strokeWidth={stroke} />
        <circle
          cx={diameter / 2}
          cy={diameter / 2}
          r={radius}
          fill="none"
          stroke="#3b82f6"
          strokeWidth={stroke}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          transform={`rotate(-90 ${diameter / 2} ${diameter / 2})`}
        />
        <text x="50%" y="50%" textAnchor="middle" dominantBaseline="middle" className={`${fontSize} font-bold fill-slate-900`}>
          {clamped}
        </text>
      </svg>
      {label && <span className="text-xs text-slate-600">{label}</span>}
    </div>
  );
}
