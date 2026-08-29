"use client";

import { useId } from "react";
import {
  DndContext,
  closestCenter,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  SortableContext,
  useSortable,
  verticalListSortingStrategy,
  arrayMove,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { GripVertical, Trash2 } from "lucide-react";
import type { CvExperienceEntry } from "@/lib/types";

function ExperienceEntryCard({
  id,
  entry,
  onChange,
  onRemove,
}: {
  id: string;
  entry: CvExperienceEntry;
  onChange: (entry: CvExperienceEntry) => void;
  onRemove: () => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id });

  return (
    <div
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      className={`rounded-lg border border-border/80 bg-card p-3 space-y-2 ${
        isDragging ? "opacity-60" : ""
      }`}
    >
      <div className="flex items-center gap-2">
        <button
          type="button"
          {...attributes}
          {...listeners}
          className="cursor-grab text-muted-foreground hover:text-foreground shrink-0"
          aria-label="Réordonner"
        >
          <GripVertical className="w-4 h-4" />
        </button>
        <input
          value={entry.title}
          onChange={(e) => onChange({ ...entry, title: e.target.value })}
          placeholder="Titre du poste"
          className="flex-1 min-w-0 text-sm font-semibold bg-transparent border-b border-transparent hover:border-border focus:border-primary focus:outline-none"
        />
        <button
          type="button"
          onClick={onRemove}
          className="text-muted-foreground hover:text-destructive shrink-0"
          aria-label="Supprimer cette expérience"
        >
          <Trash2 className="w-4 h-4" />
        </button>
      </div>
      <div className="flex gap-2 pl-6">
        <input
          value={entry.company}
          onChange={(e) => onChange({ ...entry, company: e.target.value })}
          placeholder="Entreprise"
          className="flex-1 min-w-0 text-xs bg-transparent border-b border-transparent hover:border-border focus:border-primary focus:outline-none"
        />
        <input
          value={entry.dates}
          onChange={(e) => onChange({ ...entry, dates: e.target.value })}
          placeholder="Dates"
          className="w-32 shrink-0 text-xs bg-transparent border-b border-transparent hover:border-border focus:border-primary focus:outline-none"
        />
      </div>
      <textarea
        value={entry.bullets.join("\n")}
        onChange={(e) =>
          onChange({ ...entry, bullets: e.target.value.split("\n") })
        }
        placeholder="Un point par ligne"
        rows={3}
        className="w-full ml-6 text-xs bg-muted/30 rounded-md p-2 border border-transparent hover:border-border focus:border-primary focus:outline-none resize-y"
        style={{ width: "calc(100% - 1.5rem)" }}
      />
    </div>
  );
}

export function SectionDragList({
  entries,
  onChange,
}: {
  entries: CvExperienceEntry[];
  onChange: (entries: CvExperienceEntry[]) => void;
}) {
  const idPrefix = useId();
  const ids = entries.map((_, i) => `${idPrefix}-${i}`);
  const sensors = useSensors(useSensor(PointerSensor));

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const oldIndex = ids.indexOf(String(active.id));
    const newIndex = ids.indexOf(String(over.id));
    onChange(arrayMove(entries, oldIndex, newIndex));
  };

  const updateEntry = (index: number, entry: CvExperienceEntry) => {
    const next = [...entries];
    next[index] = entry;
    onChange(next);
  };

  const removeEntry = (index: number) => {
    onChange(entries.filter((_, i) => i !== index));
  };

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCenter}
      onDragEnd={handleDragEnd}
    >
      <SortableContext items={ids} strategy={verticalListSortingStrategy}>
        <div className="space-y-2">
          {entries.map((entry, index) => (
            <ExperienceEntryCard
              key={ids[index]}
              id={ids[index]}
              entry={entry}
              onChange={(updated) => updateEntry(index, updated)}
              onRemove={() => removeEntry(index)}
            />
          ))}
        </div>
      </SortableContext>
    </DndContext>
  );
}
