import { Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * Consistent disclaimer for any AI-generated content (CV, lettre, dossier
 * d'entretien, diagnostic) - one shared message instead of each surface
 * inventing its own wording.
 */
export function AiDisclaimerNote({ className }: { className?: string }) {
  return (
    <p
      className={cn(
        "flex items-center gap-1.5 text-[11px] text-muted-foreground",
        className
      )}
    >
      <Sparkles className="w-3 h-3 shrink-0" />
      Contenu généré par IA — vérifiez les informations avant de les utiliser.
    </p>
  );
}
