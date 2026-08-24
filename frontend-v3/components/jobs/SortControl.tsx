import { Select } from "@/components/ui/Select";

export type SortOrder = "compatibility" | "recent";

const SORT_OPTIONS = [
  { value: "compatibility", label: "Meilleure compatibilité" },
  { value: "recent", label: "Plus récentes" },
];

export interface SortControlProps {
  value: SortOrder;
  onChange: (value: SortOrder) => void;
}

export function SortControl({ value, onChange }: SortControlProps) {
  return (
    <div className="w-full max-w-[220px]">
      <Select
        options={SORT_OPTIONS}
        value={value}
        onChange={(e) => onChange(e.target.value as SortOrder)}
      />
    </div>
  );
}
