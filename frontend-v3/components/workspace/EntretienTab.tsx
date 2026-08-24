import { MessagesSquare } from "lucide-react";
import { Card, CardContent } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";

export function EntretienTab() {
  return (
    <Card>
      <CardContent className="p-6">
        <EmptyState
          icon={MessagesSquare}
          title="Préparation d'entretien bientôt disponible"
          description="Cette fonctionnalité arrive dans une prochaine mise à jour : questions probables, points à mettre en avant et simulation d'entretien pour cette offre."
        />
      </CardContent>
    </Card>
  );
}
