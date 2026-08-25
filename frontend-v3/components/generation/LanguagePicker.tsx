"use client";

import { Select } from "@/components/ui/Select";

const LANGUAGES = [
  { value: "fr", label: "Français" },
  { value: "en", label: "Anglais" },
];

export function LanguagePicker({
  value,
  onChange,
}: {
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <Select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      options={LANGUAGES}
      aria-label="Langue du CV"
    />
  );
}
