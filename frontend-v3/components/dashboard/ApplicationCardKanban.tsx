"use client";

import { useState } from "react";
import { useDraggable } from "@dnd-kit/core";
import { CSS } from "@dnd-kit/utilities";
import { CalendarPlus, GripVertical } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { statusLabel, statusVariant, getInitials } from "@/lib/utils";
import { InterviewScheduleDialog } from "@/components/dashboard/InterviewScheduleDialog";
import type { ApplicationOut } from "@/lib/types";

export function ApplicationCardKanban({
  application,
  token,
  onInterviewScheduled,
}: {
  application: ApplicationOut;
  token: string;
  onInterviewScheduled: () => void;
}) {
  const [isScheduling, setIsScheduling] = useState(false);
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: `app-${application.id}`,
    data: { applicationId: application.id },
  });

  return (
    <>
      <Card
        ref={setNodeRef}
        style={{ transform: CSS.Translate.toString(transform) }}
        className={`p-3 space-y-2 ${isDragging ? "opacity-50 z-10" : ""}`}
      >
        <div className="flex items-start gap-2">
          <button
            type="button"
            {...attributes}
            {...listeners}
            className="cursor-grab active:cursor-grabbing text-muted-foreground hover:text-foreground shrink-0 mt-0.5 touch-none"
            aria-label="Déplacer cette candidature"
          >
            <GripVertical className="w-4 h-4" />
          </button>
          <div className="w-7 h-7 rounded-lg bg-primary/10 text-primary font-bold text-[10px] flex items-center justify-center shrink-0">
            {getInitials(application.company_name)}
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold text-foreground truncate">
              {application.job_title}
            </p>
            <p className="text-xs text-muted-foreground truncate">
              {application.company_name}
            </p>
          </div>
        </div>

        <div className="flex items-center justify-between gap-2 pl-6">
          <Badge variant={statusVariant(application.status)}>
            {statusLabel(application.status)}
          </Badge>
          <button
            type="button"
            onClick={() => setIsScheduling(true)}
            className="text-muted-foreground hover:text-primary shrink-0"
            aria-label="Planifier un entretien"
            title="Planifier un entretien"
          >
            <CalendarPlus className="w-4 h-4" />
          </button>
        </div>
      </Card>

      <InterviewScheduleDialog
        application={application}
        token={token}
        isOpen={isScheduling}
        onClose={() => setIsScheduling(false)}
        onScheduled={onInterviewScheduled}
      />
    </>
  );
}
