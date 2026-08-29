"use client";

import { CheckCircle2, Circle, Loader2, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";

export function AIProgressChecklist({
  steps,
  currentStepIndex,
  status,
}: {
  steps: string[];
  currentStepIndex: number;
  status: "running" | "done" | "error";
}) {
  return (
    <ul className="space-y-2.5">
      {steps.map((step, index) => {
        const stepNumber = index + 1;
        const isDone = status === "done" || stepNumber < currentStepIndex;
        const isCurrent =
          stepNumber === currentStepIndex && status === "running";
        const isFailed = stepNumber === currentStepIndex && status === "error";

        return (
          <li
            key={step}
            className={cn(
              "flex items-center gap-2.5 text-sm transition-colors",
              isDone && "text-foreground font-medium",
              isCurrent && "text-primary font-semibold",
              isFailed && "text-destructive font-semibold",
              !isDone && !isCurrent && !isFailed && "text-muted-foreground"
            )}
          >
            {isFailed ? (
              <XCircle className="w-4 h-4 shrink-0 text-destructive" />
            ) : isCurrent ? (
              <Loader2 className="w-4 h-4 shrink-0 animate-spin text-primary" />
            ) : isDone ? (
              <CheckCircle2 className="w-4 h-4 shrink-0 text-success" />
            ) : (
              <Circle className="w-4 h-4 shrink-0" />
            )}
            {step}
          </li>
        );
      })}
    </ul>
  );
}
