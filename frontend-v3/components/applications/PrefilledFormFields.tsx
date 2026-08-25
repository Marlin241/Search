import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { Textarea } from "@/components/ui/Textarea";
import type { FormField } from "@/lib/types";

export function PrefilledFormFields({
  fields,
  onChange,
}: {
  fields: FormField[];
  onChange: (name: string, value: string) => void;
}) {
  return (
    <div className="space-y-3">
      {fields.map((field) => {
        const needsCompletion = field.required && !field.value;
        const hint = [
          field.is_custom ? "généré par l'IA — à vérifier" : null,
          needsCompletion ? "à compléter" : null,
        ]
          .filter(Boolean)
          .join(" · ") || undefined;

        if (field.field_type === "textarea") {
          return (
            <Textarea
              key={field.name}
              label={field.label}
              required={field.required}
              hint={hint}
              value={field.value ?? ""}
              onChange={(e) => onChange(field.name, e.target.value)}
              rows={3}
            />
          );
        }
        if (field.field_type === "select") {
          return (
            <div key={field.name} className="space-y-1">
              <Select
                label={field.label}
                required={field.required}
                options={(field.options ?? []).map((opt) => ({ value: opt, label: opt }))}
                placeholder="Sélectionnez…"
                value={field.value ?? ""}
                onChange={(e) => onChange(field.name, e.target.value)}
              />
              {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
            </div>
          );
        }
        return (
          <Input
            key={field.name}
            label={field.label}
            required={field.required}
            hint={hint}
            value={field.value ?? ""}
            onChange={(e) => onChange(field.name, e.target.value)}
          />
        );
      })}
    </div>
  );
}
