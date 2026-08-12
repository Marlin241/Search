import { Button } from "./ui/Button";
import { Card } from "./ui/Card";

interface ConfirmDialogProps {
  message: string;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmDialog({ message, onConfirm, onCancel }: ConfirmDialogProps) {
  return (
    <div className="fixed inset-0 flex items-center justify-center bg-slate-900/40">
      <Card className="w-full max-w-sm p-6">
        <p className="text-sm text-slate-800 dark:text-slate-100">{message}</p>
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="secondary" size="sm" onClick={onCancel}>
            Annuler
          </Button>
          <Button variant="danger" size="sm" onClick={onConfirm}>
            Supprimer
          </Button>
        </div>
      </Card>
    </div>
  );
}
