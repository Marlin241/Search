"use client";

import { useState } from "react";
import { HelpCircle } from "lucide-react";
import { Dialog } from "@/components/ui/Dialog";
import { Button } from "@/components/ui/Button";

const ITEMS: { title: string; text: string }[] = [
  {
    title: "Score Global",
    text: "La note globale de votre candidature pour cette offre. Elle combine la Structure ATS et la Sémantique ci-dessous.",
  },
  {
    title: "Structure ATS",
    text: "Est-ce que la mise en page de votre CV peut être lue correctement par les logiciels de tri automatique des recruteurs (ATS) ? Un tableau, une image ou une colonne mal placée peut faire disparaître des informations à leurs yeux, même si un humain les lirait sans problème.",
  },
  {
    title: "Sémantique",
    text: "Est-ce que le contenu de votre CV correspond au vocabulaire et aux compétences demandées dans l'offre ? Calculé par notre IA à partir du texte de l'offre.",
  },
];

const THRESHOLDS = [
  { range: "70 % et plus", label: "Bon", dotClass: "bg-success" },
  { range: "40 % à 69 %", label: "Moyen", dotClass: "bg-warning" },
  { range: "Moins de 40 %", label: "Faible", dotClass: "bg-destructive" },
];

export function ScoreLegend() {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <>
      <Button
        variant="ghost"
        size="sm"
        icon={<HelpCircle className="w-4 h-4" />}
        onClick={() => setIsOpen(true)}
        title="Que veulent dire ces pourcentages ?"
        aria-label="Que veulent dire ces pourcentages ?"
      />
      <Dialog
        isOpen={isOpen}
        onClose={() => setIsOpen(false)}
        title="Que veulent dire ces pourcentages ?"
        description="Un guide simple pour lire vos scores."
      >
        <div className="space-y-4 mt-2">
          {ITEMS.map((item) => (
            <div key={item.title} className="space-y-1">
              <h4 className="text-sm font-bold font-display text-foreground">
                {item.title}
              </h4>
              <p className="text-xs text-muted-foreground">{item.text}</p>
            </div>
          ))}

          <div className="border-t border-border pt-3 space-y-1.5">
            <h4 className="text-sm font-bold font-display text-foreground">
              Comment lire un pourcentage
            </h4>
            {THRESHOLDS.map((t) => (
              <div key={t.label} className="flex items-center gap-2 text-xs">
                <span className={`w-2 h-2 rounded-full shrink-0 ${t.dotClass}`} />
                <span className="font-semibold text-foreground">{t.label}</span>
                <span className="text-muted-foreground">— {t.range}</span>
              </div>
            ))}
          </div>
        </div>
      </Dialog>
    </>
  );
}
