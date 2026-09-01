"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Textarea } from "@/components/ui/Textarea";
import { requestAccess } from "@/lib/api";

export function AccessRequestForm() {
  const [email, setEmail] = useState("");
  const [note, setNote] = useState("");
  const [company, setCompany] = useState(""); // honeypot
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim()) {
      toast.error("Indique ton email.");
      return;
    }
    setSubmitting(true);
    try {
      await requestAccess(email.trim(), note.trim());
      setDone(true);
    } catch (err) {
      toast.error(
        err instanceof Error
          ? err.message
          : "Une erreur est survenue. Réessaie."
      );
    } finally {
      setSubmitting(false);
    }
  };

  if (done) {
    return (
      <div className="rounded-2xl border border-success/30 bg-success/10 p-6 text-center">
        <p className="font-display text-lg font-semibold text-foreground">
          Merci, c&apos;est noté.
        </p>
        <p className="mt-1 text-sm text-muted-foreground">
          Un email de confirmation vient de t&apos;être envoyé. On te
          recontacte dès qu&apos;une place se libère.
        </p>
      </div>
    );
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4">
      {/* Honeypot : hors écran, invisible aux humains, appât pour les bots */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute left-[-9999px] h-0 w-0 overflow-hidden"
      >
        <label>
          Entreprise
          <input
            type="text"
            tabIndex={-1}
            autoComplete="off"
            value={company}
            onChange={(e) => setCompany(e.target.value)}
          />
        </label>
      </div>

      <Input
        label="Ton email"
        type="email"
        placeholder="prenom.nom@exemple.com"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        required
      />
      <Textarea
        label="Où en es-tu dans ta recherche ? (optionnel)"
        placeholder="Ex : développeur back-end à Dakar, en poste, je regarde ailleurs."
        value={note}
        onChange={(e) => setNote(e.target.value)}
        rows={3}
      />
      <Button
        type="submit"
        variant="primary"
        size="lg"
        fullWidth
        isLoading={submitting}
      >
        Demander un accès
      </Button>
      <p className="text-center text-xs text-muted-foreground">
        Beta fermée — on ouvre l&apos;accès progressivement.
      </p>
    </form>
  );
}
