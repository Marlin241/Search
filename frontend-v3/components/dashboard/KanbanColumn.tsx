"use client";

import { useDroppable } from "@dnd-kit/core";
import { cn } from "@/lib/utils";

export function KanbanColumn({
  id,
  title,
  count,
  children,
  droppable = true,
}: {
  id: string;
  title: string;
  count: number;
  children: React.ReactNode;
  droppable?: boolean;
}) {
  const { setNodeRef, isOver } = useDroppable({ id, disabled: !droppable });

  return (
    <div className="flex flex-col min-w-[260px] w-[260px] shrink-0">
      <div className="flex items-center justify-between px-1 pb-2">
        <h3 className="text-sm font-bold text-foreground">{title}</h3>
        <span className="text-xs font-semibold text-muted-foreground bg-muted rounded-full px-2 py-0.5">
          {count}
        </span>
      </div>
      <div
        ref={setNodeRef}
        className={cn(
          "flex-1 min-h-[120px] space-y-2 rounded-xl border border-dashed border-border/60 bg-muted/20 p-2 transition-colors",
          isOver && droppable && "border-primary/60 bg-primary/5"
        )}
      >
        {children}
      </div>
    </div>
  );
}
