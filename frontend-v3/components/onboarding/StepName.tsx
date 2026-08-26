"use client";

import { Input } from "@/components/ui/Input";

export interface StepNameProps {
  firstName: string;
  onFirstNameChange: (value: string) => void;
  lastName: string;
  onLastNameChange: (value: string) => void;
}

export function StepName({
  firstName,
  onFirstNameChange,
  lastName,
  onLastNameChange,
}: StepNameProps) {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="font-display text-2xl font-bold text-foreground">
          Comment tu t'appelles ?
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Ce nom apparaîtra sur tes CV générés et tes candidatures.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Input
          label="Prénom"
          placeholder="ex : Camille"
          value={firstName}
          onChange={(e) => onFirstNameChange(e.target.value)}
          required
          autoFocus
        />
        <Input
          label="Nom"
          placeholder="ex : Martin"
          value={lastName}
          onChange={(e) => onLastNameChange(e.target.value)}
          required
        />
      </div>
    </div>
  );
}
