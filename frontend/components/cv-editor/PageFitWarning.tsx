import { Info } from "lucide-react";

export function PageFitWarning() {
  return (
    <div className="flex items-start gap-2 text-xs text-muted-foreground bg-muted/30 rounded-lg p-2.5">
      <Info className="w-3.5 h-3.5 shrink-0 mt-0.5" />
      <span>
        Astuce : gardez votre CV sur une seule page pour un meilleur passage
        des filtres ATS. Vérifiez l&apos;aperçu à droite après chaque modification.
      </span>
    </div>
  );
}
