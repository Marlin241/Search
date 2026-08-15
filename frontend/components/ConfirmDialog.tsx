import { Button } from "./ui/Button";
import { Card } from "./ui/Card";

interface ConfirmDialogProps {
  message: string;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmDialog({ message, onConfirm, onCancel }: ConfirmDialogProps) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 p-5">
      <Card className="w-full max-w-sm rounded-[26px] p-6 shadow-pop">
        <p className="text-sm font-semibold text-ink">{message}</p>
        <div className="mt-5 flex justify-end gap-2">
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
