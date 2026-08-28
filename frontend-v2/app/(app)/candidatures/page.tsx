"use client";

import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Send,
  Building,
  CheckCircle2,
  Clock,
  AlertCircle,
  ExternalLink,
  Sparkles,
  Download,
  Check,
  Search,
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import {
  listApplications,
  getPrefilledForm,
  confirmApplication,
  markApplicationSentManually,
  downloadCv,
  downloadLetter,
} from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Card, CardContent } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Input } from "@/components/ui/Input";
import { ScoreRing } from "@/components/ui/ScoreRing";
import { EmptyState } from "@/components/ui/EmptyState";
import { Dialog } from "@/components/ui/Dialog";
import {
  cn,
  formatDate,
  formatRelativeTime,
  getInitials,
  statusLabel,
  statusVariant,
  sourceLabel,
} from "@/lib/utils";
import type { ApplicationOut, FormField } from "@/lib/types";

const STAGES = [
  { id: "all", label: "Toutes" },
  { id: "en_cours", label: "En cours" },
  { id: "a_soumettre_manuellement", label: "À envoyer" },
  { id: "soumise", label: "Envoyées" },
];

export default function CandidaturesPage() {
  const { token } = useAuth();

  const [applications, setApplications] = useState<ApplicationOut[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [activeFilter, setActiveFilter] = useState("all");

  // ATS Prefilled form review modal
  const [selectedApp, setSelectedApp] = useState<ApplicationOut | null>(null);
  const [formFields, setFormFields] = useState<FormField[]>([]);
  const [isFormModalOpen, setIsFormModalOpen] = useState(false);
  const [isLoadingForm, setIsLoadingForm] = useState(false);
  const [isSubmittingForm, setIsSubmittingForm] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const fetchApps = async () => {
    if (!token) return;
    setIsLoading(true);
    try {
      const data = await listApplications(token);
      setApplications(data || []);
    } catch (err) {
      console.error("Failed to list applications:", err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchApps();
  }, [token]);

  const filteredApps = applications.filter((app) => {
    if (activeFilter === "all") return true;
    if (activeFilter === "soumise") return app.status.includes("soumise");
    return app.status === activeFilter;
  });

  const handleOpenFormReview = async (app: ApplicationOut) => {
    if (!token) return;
    setSelectedApp(app);
    setIsFormModalOpen(true);
    setIsLoadingForm(true);
    setFormError(null);

    try {
      const form = await getPrefilledForm(token, app.id);
      setFormFields(form.fields || []);
    } catch (err: any) {
      setFormError(err?.detail || "Impossible de charger le formulaire de l'offre.");
    } finally {
      setIsLoadingForm(false);
    }
  };

  const handleConfirmSubmit = async () => {
    if (!token || !selectedApp) return;
    setIsSubmittingForm(true);
    setFormError(null);

    try {
      await confirmApplication(token, selectedApp.id, {
        fields: formFields,
        override_needs_review: true,
      });
      setIsFormModalOpen(false);
      fetchApps();
    } catch (err: any) {
      setFormError(err?.detail || "Erreur lors de la soumission de la candidature.");
    } finally {
      setIsSubmittingForm(false);
    }
  };

  const handleMarkSent = async (appId: number) => {
    if (!token) return;
    try {
      await markApplicationSentManually(token, appId);
      fetchApps();
    } catch (err) {
      console.error("Failed to mark sent:", err);
    }
  };

  return (
    <div className="space-y-8 animate-fade-in pb-20 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-display font-bold text-foreground">
            Suivi des candidatures
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Pilotez chaque étape de vos candidatures et visualisez vos progrès.
          </p>
        </div>

        {/* Filter tabs */}
        <div className="bg-muted/80 p-1 rounded-xl flex items-center gap-1 border border-border/40">
          {STAGES.map((s) => (
            <button
              key={s.id}
              onClick={() => setActiveFilter(s.id)}
              className={cn(
                "px-3 py-1.5 text-xs font-semibold rounded-lg transition-all",
                activeFilter === s.id
                  ? "bg-card text-foreground shadow-soft"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              {s.label}
            </button>
          ))}
        </div>
      </div>

      {/* Applications list */}
      <div className="space-y-4">
        {isLoading ? (
          Array.from({ length: 4 }).map((_, i) => (
            <Card key={i} className="p-5">
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 rounded-xl bg-muted animate-pulse shrink-0" />
                <div className="space-y-2 flex-1">
                  <div className="h-4 w-1/3 bg-muted rounded animate-pulse" />
                  <div className="h-3 w-1/4 bg-muted rounded animate-pulse" />
                </div>
              </div>
            </Card>
          ))
        ) : filteredApps.length > 0 ? (
          filteredApps.map((app) => (
            <Card
              key={app.id}
              className="p-5 hover:border-primary/40 transition-all shadow-sm space-y-4"
            >
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                {/* Left details */}
                <div className="flex items-start gap-4 min-w-0">
                  <div className="w-12 h-12 rounded-2xl bg-primary/10 text-primary font-bold text-sm flex items-center justify-center shrink-0">
                    {getInitials(app.company_name)}
                  </div>
                  <div className="min-w-0 space-y-1">
                    <div className="flex items-center gap-2">
                      <h3 className="text-base font-bold text-foreground truncate">
                        {app.job_title}
                      </h3>
                      <a
                        href={app.offer_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-muted-foreground hover:text-foreground shrink-0"
                      >
                        <ExternalLink className="w-3.5 h-3.5" />
                      </a>
                    </div>
                    <p className="text-xs text-muted-foreground">
                      {app.company_name} · Source : {sourceLabel(app.source)} · Créée le {formatDate(app.created_at)}
                    </p>
                  </div>
                </div>

                {/* Status and Actions */}
                <div className="flex items-center gap-3 self-end sm:self-center">
                  <Badge variant={statusVariant(app.status)}>
                    {statusLabel(app.status)}
                  </Badge>

                  {app.ats_type && app.status === "en_cours" && (
                    <Button
                      variant="primary"
                      size="sm"
                      onClick={() => handleOpenFormReview(app)}
                      icon={<Sparkles className="w-3.5 h-3.5" />}
                    >
                      Postuler via ATS
                    </Button>
                  )}

                  {app.status === "a_soumettre_manuellement" && (
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => handleMarkSent(app.id)}
                      icon={<Check className="w-3.5 h-3.5" />}
                    >
                      Marquer envoyée
                    </Button>
                  )}
                </div>
              </div>

              {/* Diagnostic preview row */}
              {app.diagnostic && (
                <div className="flex flex-wrap items-center justify-between gap-3 pt-3 border-t border-border/50 text-xs text-muted-foreground">
                  <div className="flex items-center gap-3">
                    <span className="font-semibold text-foreground">Score compatibilité :</span>
                    <span className="font-bold text-primary">{app.diagnostic.overall_score}%</span>
                  </div>

                  <div className="flex items-center gap-2">
                    <button
                      onClick={async () => {
                        try {
                          const blob = await downloadCv(token!, app.diagnostic_id);
                          const url = window.URL.createObjectURL(blob);
                          const a = document.createElement("a");
                          a.href = url;
                          a.download = `cv_${app.company_name.toLowerCase().replace(/\s+/g, "_")}.pdf`;
                          a.click();
                        } catch (err) {
                          alert("Le CV personnalisé n'a pas encore été généré pour cette candidature.");
                        }
                      }}
                      className="inline-flex items-center gap-1.5 text-xs text-primary font-semibold hover:underline"
                    >
                      <Download className="w-3.5 h-3.5" /> Télécharger le CV optimisé
                    </button>
                  </div>
                </div>
              )}
            </Card>
          ))
        ) : (
          <EmptyState
            icon={Send}
            title="Aucune candidature trouvée"
            description="Explorez les offres d'emploi pour postuler et démarrer votre suivi."
          />
        )}
      </div>

      {/* Prefilled Form Modal */}
      <Dialog
        isOpen={isFormModalOpen}
        onClose={() => setIsFormModalOpen(false)}
        title={`Candidature ATS : ${selectedApp?.company_name || ""}`}
        description="Vérifiez les champs pré-remplis par notre IA avant d'envoyer la candidature automatiquement."
      >
        <div className="space-y-4 mt-4 max-h-[65vh] overflow-y-auto pr-1">
          {isLoadingForm ? (
            <div className="p-8 text-center space-y-3">
              <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin mx-auto" />
              <p className="text-xs text-muted-foreground">
                Récupération du formulaire ATS et génération des réponses adaptées...
              </p>
            </div>
          ) : formError ? (
            <div className="p-3 bg-destructive/10 text-destructive text-xs rounded-xl flex items-start gap-2">
              <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
              <p>{formError}</p>
            </div>
          ) : (
            <div className="space-y-3">
              {formFields.map((field, idx) => (
                <div key={idx} className="space-y-1">
                  <Input
                    label={field.label}
                    value={field.value || ""}
                    onChange={(e) => {
                      const updated = [...formFields];
                      updated[idx].value = e.target.value;
                      setFormFields(updated);
                    }}
                    required={field.required}
                  />
                </div>
              ))}
            </div>
          )}

          <div className="flex justify-end gap-2 pt-4 border-t border-border/50">
            <Button
              type="button"
              variant="ghost"
              onClick={() => setIsFormModalOpen(false)}
            >
              Annuler
            </Button>
            <Button
              type="button"
              variant="primary"
              isLoading={isSubmittingForm}
              onClick={handleConfirmSubmit}
              disabled={isLoadingForm || !!formError}
            >
              Confirmer et envoyer
            </Button>
          </div>
        </div>
      </Dialog>
    </div>
  );
}
