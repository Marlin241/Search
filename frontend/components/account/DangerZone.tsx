"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Download, Trash2 } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { deleteAccount, exportAccount } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Dialog } from "@/components/ui/Dialog";

export function DangerZone() {
  const { token, logout } = useAuth();
  const router = useRouter();

  const [isOpen, setIsOpen] = useState(false);
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleExport = async () => {
    if (!token) return;
    try {
      const blob = await exportAccount(token);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "mes-donnees.json";
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      toast.error("Échec de l'export. Réessaie.");
    }
  };

  const handleDelete = async () => {
    if (!token) return;
    setError(null);
    setBusy(true);
    try {
      await deleteAccount(token, password);
      logout();
      router.push("/login");
    } catch (err: any) {
      setError(err?.message || "Échec de la suppression.");
      setBusy(false);
    }
  };

  return (
    <div className="space-y-4 rounded-xl border border-destructive/30 p-4">
      <h3 className="text-base font-bold font-display text-foreground">
        Zone de danger
      </h3>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-sm font-medium text-foreground">
            Exporter mes données
          </p>
          <p className="text-xs text-muted-foreground">
            Télécharge un fichier JSON avec toutes tes données.
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          icon={<Download className="w-4 h-4" />}
          onClick={handleExport}
        >
          Exporter
        </Button>
      </div>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-sm font-medium text-foreground">
            Supprimer mon compte
          </p>
          <p className="text-xs text-muted-foreground">
            Action définitive : compte, CV, diagnostics, candidatures et
            documents générés seront supprimés.
          </p>
        </div>
        <Button
          variant="danger"
          size="sm"
          icon={<Trash2 className="w-4 h-4" />}
          onClick={() => setIsOpen(true)}
        >
          Supprimer
        </Button>
      </div>

      <Dialog
        isOpen={isOpen}
        onClose={() => setIsOpen(false)}
        title="Supprimer définitivement mon compte"
      >
        <div className="space-y-4">
          <p className="text-sm text-muted-foreground">
            Cette action est irréversible. Saisis ton mot de passe pour
            confirmer.
          </p>
          {error && (
            <div className="p-3 bg-destructive/10 border border-destructive/20 text-destructive text-xs rounded-xl">
              {error}
            </div>
          )}
          <Input
            label="Mot de passe"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          <div className="flex justify-end gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setIsOpen(false)}
            >
              Annuler
            </Button>
            <Button
              variant="danger"
              size="sm"
              isLoading={busy}
              onClick={handleDelete}
            >
              Supprimer mon compte
            </Button>
          </div>
        </div>
      </Dialog>
    </div>
  );
}
