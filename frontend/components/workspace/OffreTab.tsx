import { ExternalLink, MapPin } from "lucide-react";
import { Card, CardContent } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { sourceLabel } from "@/lib/utils";
import type { SavedJobOut } from "@/lib/types";

const APPLICATION_STATUS_LABELS: Record<string, string> = {
  en_cours: "En cours",
  soumise_auto: "Soumise automatiquement",
  a_soumettre_manuellement: "À soumettre manuellement",
  soumise_manuelle_confirmee: "Envoyée manuellement",
  echec_soumission: "Échec de soumission",
};

export function OffreTab({ savedJob }: { savedJob: SavedJobOut }) {
  return (
    <Card>
      <CardContent className="p-6 space-y-5">
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 p-3.5 bg-muted/40 rounded-xl border border-border/60 text-xs">
          <div>
            <span className="text-muted-foreground block text-[10px] uppercase font-semibold">Entreprise</span>
            <span className="font-bold text-foreground">{savedJob.company}</span>
          </div>
          <div>
            <span className="text-muted-foreground block text-[10px] uppercase font-semibold">Localisation</span>
            <span className="font-bold text-foreground flex items-center gap-1">
              {savedJob.location && <MapPin className="w-3 h-3 text-muted-foreground/80" />}
              {savedJob.location || "Non précisée"}
            </span>
          </div>
          <div>
            <span className="text-muted-foreground block text-[10px] uppercase font-semibold">Source</span>
            <span className="font-bold text-primary">{sourceLabel(savedJob.source)}</span>
          </div>
          {savedJob.salary && (
            <div>
              <span className="text-muted-foreground block text-[10px] uppercase font-semibold">Rémunération</span>
              <span className="font-bold text-success">{savedJob.salary}</span>
            </div>
          )}
          {savedJob.application_status && (
            <div>
              <span className="text-muted-foreground block text-[10px] uppercase font-semibold">Candidature</span>
              <Badge variant="accent">
                {APPLICATION_STATUS_LABELS[savedJob.application_status] || savedJob.application_status}
              </Badge>
            </div>
          )}
        </div>

        <div className="space-y-2">
          <h4 className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
            Description du poste
          </h4>
          <div className="p-4 rounded-xl bg-card border border-border text-xs leading-relaxed text-foreground whitespace-pre-line max-h-[50vh] overflow-y-auto">
            {savedJob.snippet || "Aucun extrait textuel disponible pour cette offre."}
          </div>
          {!savedJob.has_full_offer_text && (
            <p className="text-[11px] text-muted-foreground">
              Récupération du texte complet de l'offre en cours en arrière-plan...
            </p>
          )}
        </div>

        <a
          href={savedJob.offer_url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground font-medium"
        >
          <ExternalLink className="w-3.5 h-3.5" />
          Consulter l'offre originale sur {sourceLabel(savedJob.source)}
        </a>
      </CardContent>
    </Card>
  );
}
