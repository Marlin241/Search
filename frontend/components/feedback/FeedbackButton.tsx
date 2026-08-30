"use client";

import { useState } from "react";
import { usePathname } from "next/navigation";
import { toast } from "sonner";
import { MessageSquarePlus } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { sendFeedback } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Dialog } from "@/components/ui/Dialog";
import { Textarea } from "@/components/ui/Textarea";

export function FeedbackButton() {
  const { token } = useAuth();
  const pathname = usePathname();

  const [open, setOpen] = useState(false);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  if (!token) return null;

  const submit = async () => {
    const trimmed = message.trim();
    if (!trimmed) return;
    setBusy(true);
    try {
      await sendFeedback(token, pathname, trimmed);
      toast.success("Merci pour ton retour !");
      setMessage("");
      setOpen(false);
    } catch {
      toast.error("Échec de l'envoi, réessaie.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="fixed bottom-20 right-4 z-40 flex items-center gap-2 rounded-full bg-primary-600 px-4 py-2.5 text-xs font-semibold text-white shadow-lift transition-transform hover:scale-105 lg:bottom-4"
      >
        <MessageSquarePlus className="h-4 w-4" />
        Donner mon avis
      </button>

      <Dialog
        isOpen={open}
        onClose={() => setOpen(false)}
        title="Donner mon avis"
        description="Un bug, une idée, une gêne ? Dis-nous tout — ça aide vraiment."
      >
        <div className="space-y-4">
          <Textarea
            label="Ton message"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            rows={5}
            placeholder="Ce qui ne va pas, ou ce qui te ferait gagner du temps…"
          />
          <div className="flex justify-end gap-2">
            <Button variant="ghost" size="sm" onClick={() => setOpen(false)}>
              Annuler
            </Button>
            <Button
              size="sm"
              isLoading={busy}
              disabled={!message.trim()}
              onClick={submit}
            >
              Envoyer
            </Button>
          </div>
        </div>
      </Dialog>
    </>
  );
}
