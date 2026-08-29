"use client";

import { Plus } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { SectionDragList } from "@/components/cv-editor/SectionDragList";
import type { RewrittenCv } from "@/lib/types";

export function CvEditorForm({
  content,
  onChange,
}: {
  content: RewrittenCv;
  onChange: (content: RewrittenCv) => void;
}) {
  return (
    <div className="space-y-6">
      <div className="space-y-1.5">
        <label className="block text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Résumé
        </label>
        <textarea
          value={content.summary}
          onChange={(e) => onChange({ ...content, summary: e.target.value })}
          rows={3}
          className="w-full text-sm bg-card rounded-lg border border-input p-2.5 focus:outline-none focus:ring-2 focus:ring-primary/40 focus:border-primary resize-y"
        />
      </div>

      <div className="space-y-1.5">
        <div className="flex items-center justify-between">
          <label className="block text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Expérience
          </label>
          <Button
            variant="ghost"
            size="sm"
            icon={<Plus className="w-3.5 h-3.5" />}
            onClick={() =>
              onChange({
                ...content,
                experience: [
                  ...content.experience,
                  { title: "", company: "", dates: "", bullets: [""] },
                ],
              })
            }
          >
            Ajouter
          </Button>
        </div>
        <SectionDragList
          entries={content.experience}
          onChange={(experience) => onChange({ ...content, experience })}
        />
      </div>

      <div className="space-y-1.5">
        <label className="block text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Formation (une entrée par ligne)
        </label>
        <textarea
          value={content.education.join("\n")}
          onChange={(e) =>
            onChange({ ...content, education: e.target.value.split("\n") })
          }
          rows={2}
          className="w-full text-sm bg-card rounded-lg border border-input p-2.5 focus:outline-none focus:ring-2 focus:ring-primary/40 focus:border-primary resize-y"
        />
      </div>

      <div className="space-y-1.5">
        <label className="block text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Compétences (séparées par des virgules)
        </label>
        <textarea
          value={content.skills.join(", ")}
          onChange={(e) =>
            onChange({
              ...content,
              skills: e.target.value.split(",").map((s) => s.trim()),
            })
          }
          rows={2}
          className="w-full text-sm bg-card rounded-lg border border-input p-2.5 focus:outline-none focus:ring-2 focus:ring-primary/40 focus:border-primary resize-y"
        />
      </div>
    </div>
  );
}
