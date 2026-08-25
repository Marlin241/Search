"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import {
  DndContext,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import { Bookmark } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { Skeleton } from "@/components/ui/Skeleton";
import { EmptyState } from "@/components/ui/EmptyState";
import { KanbanColumn } from "@/components/dashboard/KanbanColumn";
import { ApplicationCardKanban } from "@/components/dashboard/ApplicationCardKanban";
import { getDashboardKanban, updateFunnelStage } from "@/lib/api";
import type { ApplicationOut, FunnelStage, KanbanBoardOut } from "@/lib/types";

const COLUMNS: { stage: FunnelStage; title: string }[] = [
  { stage: "postule", title: "Postulé" },
  { stage: "entretien_programme", title: "Entretien programmé" },
  { stage: "proposition", title: "Proposition" },
  { stage: "refusee", title: "Refusée" },
];

function SavedJobCardMuted({ title, company }: { title: string; company: string }) {
  return (
    <Card className="p-3 opacity-70 bg-muted/30 border-dashed">
      <div className="flex items-start gap-2">
        <Bookmark className="w-4 h-4 text-muted-foreground shrink-0 mt-0.5" />
        <div className="min-w-0">
          <p className="text-sm font-semibold text-foreground truncate">{title}</p>
          <p className="text-xs text-muted-foreground truncate">{company}</p>
        </div>
      </div>
    </Card>
  );
}

export function KanbanBoard({ token }: { token: string }) {
  const [board, setBoard] = useState<KanbanBoardOut | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 4 } }));

  const refresh = () => {
    getDashboardKanban(token)
      .then(setBoard)
      .catch(() => toast.error("Impossible de charger le tableau."));
  };

  useEffect(() => {
    setIsLoading(true);
    getDashboardKanban(token)
      .then(setBoard)
      .catch(() => toast.error("Impossible de charger le tableau."))
      .finally(() => setIsLoading(false));
  }, [token]);

  const handleDragEnd = async (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || !board) return;

    const applicationId = active.data.current?.applicationId as number | undefined;
    const targetStage = over.id as FunnelStage;
    if (!applicationId) return;
    if (!COLUMNS.some((c) => c.stage === targetStage)) return;

    let sourceStage: FunnelStage | null = null;
    for (const { stage } of COLUMNS) {
      if (board[stage].some((a) => a.id === applicationId)) {
        sourceStage = stage;
        break;
      }
    }
    if (!sourceStage || sourceStage === targetStage) return;

    const moved = board[sourceStage].find((a) => a.id === applicationId) as ApplicationOut;
    const previousBoard = board;

    setBoard({
      ...board,
      [sourceStage]: board[sourceStage].filter((a) => a.id !== applicationId),
      [targetStage]: [{ ...moved, funnel_stage: targetStage }, ...board[targetStage]],
    });

    try {
      await updateFunnelStage(token, applicationId, targetStage);
    } catch (err: any) {
      setBoard(previousBoard);
      toast.error(err?.detail || "Impossible de déplacer cette candidature.");
    }
  };

  if (isLoading) {
    return (
      <div className="flex gap-3 overflow-x-auto pb-2">
        {[...Array(5)].map((_, i) => (
          <Skeleton key={i} className="h-64 w-[260px] shrink-0 rounded-xl" />
        ))}
      </div>
    );
  }

  if (!board) return null;

  const isEmpty =
    board.sauvegardees.length === 0 &&
    COLUMNS.every(({ stage }) => board[stage].length === 0);

  if (isEmpty) {
    return (
      <EmptyState
        icon={Bookmark}
        title="Aucune candidature pour l'instant"
        description="Sauvegardez une offre puis lancez une candidature pour la voir apparaître ici."
        action={
          <Link href="/offres" className="text-sm font-semibold text-primary hover:underline">
            Voir les offres
          </Link>
        }
      />
    );
  }

  return (
    <DndContext sensors={sensors} onDragEnd={handleDragEnd}>
      <div className="flex gap-3 overflow-x-auto pb-2">
        <KanbanColumn id="sauvegardees" title="Sauvegardées" count={board.sauvegardees.length} droppable={false}>
          {board.sauvegardees.map((sj) => (
            <SavedJobCardMuted key={sj.id} title={sj.title} company={sj.company} />
          ))}
        </KanbanColumn>

        {COLUMNS.map(({ stage, title }) => (
          <KanbanColumn key={stage} id={stage} title={title} count={board[stage].length}>
            {board[stage].map((application) => (
              <ApplicationCardKanban
                key={application.id}
                application={application}
                token={token}
                onInterviewScheduled={refresh}
                onApplicationUpdated={refresh}
              />
            ))}
          </KanbanColumn>
        ))}
      </div>
    </DndContext>
  );
}
