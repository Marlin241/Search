import type { InterviewType } from "@/lib/types";

export const INTERVIEW_TYPE_LABELS: Record<InterviewType, string> = {
  rh: "RH",
  manager: "Manager",
  direction: "Direction",
  jury: "Jury",
  autre: "Autre",
};

export const INTERVIEW_TYPE_COLORS: Record<InterviewType, string> = {
  rh: "bg-primary/15 text-primary border-primary/30",
  manager: "bg-accent/15 text-accent-foreground border-accent/30",
  direction: "bg-warning/15 text-warning-dark border-warning/30",
  jury: "bg-destructive/15 text-destructive border-destructive/30",
  autre: "bg-secondary text-secondary-foreground border-border/50",
};

const TYPES: InterviewType[] = ["rh", "manager", "direction", "jury", "autre"];

export function CalendarLegend() {
  return (
    <div className="flex flex-wrap items-center gap-2">
      {TYPES.map((type) => (
        <span
          key={type}
          className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs font-medium ${INTERVIEW_TYPE_COLORS[type]}`}
        >
          <span className="w-1.5 h-1.5 rounded-full bg-current" />
          {INTERVIEW_TYPE_LABELS[type]}
        </span>
      ))}
    </div>
  );
}
