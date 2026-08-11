import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { PrefilledFormReview } from "./PrefilledFormReview";
import type { FormField } from "@/lib/types";

const fields: FormField[] = [
  { name: "first_name", label: "First name", field_type: "text", required: true, options: null, value: "Jane", is_custom: false },
  { name: "custom_why", label: "Why this role?", field_type: "textarea", required: false, options: null, value: "Réponse générée.", is_custom: true },
];

const selectField: FormField = {
  name: "work_type",
  label: "Type de poste",
  field_type: "select",
  required: true,
  options: ["Temps plein", "Temps partiel", "Stage"],
  value: "Temps plein",
  is_custom: false,
};

describe("PrefilledFormReview", () => {
  it("renders each field's current value", () => {
    render(<PrefilledFormReview fields={fields} onConfirm={vi.fn()} onCancel={vi.fn()} isConfirming={false} />);
    expect(screen.getByLabelText(/first name/i)).toHaveValue("Jane");
    expect(screen.getByLabelText(/why this role/i)).toHaveValue("Réponse générée.");
  });

  it("flags custom fields as LLM-generated", () => {
    render(<PrefilledFormReview fields={fields} onConfirm={vi.fn()} onCancel={vi.fn()} isConfirming={false} />);
    expect(screen.getByText(/généré par l'ia/i)).toBeInTheDocument();
  });

  it("lets the user edit a field before confirming", () => {
    const onConfirm = vi.fn();
    render(<PrefilledFormReview fields={fields} onConfirm={onConfirm} onCancel={vi.fn()} isConfirming={false} />);

    fireEvent.change(screen.getByLabelText(/first name/i), { target: { value: "Janet" } });
    fireEvent.click(screen.getByRole("button", { name: /envoyer la candidature/i }));

    expect(onConfirm).toHaveBeenCalledWith([
      { ...fields[0], value: "Janet" },
      fields[1],
    ]);
  });

  it("calls onCancel when cancel is clicked", () => {
    const onCancel = vi.fn();
    render(<PrefilledFormReview fields={fields} onConfirm={vi.fn()} onCancel={onCancel} isConfirming={false} />);
    fireEvent.click(screen.getByRole("button", { name: /annuler/i }));
    expect(onCancel).toHaveBeenCalled();
  });

  it("disables the confirm button while confirming", () => {
    render(<PrefilledFormReview fields={fields} onConfirm={vi.fn()} onCancel={vi.fn()} isConfirming={true} />);
    expect(screen.getByRole("button", { name: /envoi en cours/i })).toBeDisabled();
  });

  it("renders a select field as a real dropdown with its options and current value", () => {
    render(<PrefilledFormReview fields={[selectField]} onConfirm={vi.fn()} onCancel={vi.fn()} isConfirming={false} />);
    const select = screen.getByLabelText(/type de poste/i);
    expect(select.tagName).toBe("SELECT");
    expect(select).toHaveValue("Temps plein");
    expect(screen.getByRole("option", { name: "Temps plein" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Temps partiel" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Stage" })).toBeInTheDocument();
  });

  it("lets the user change a select field's value before confirming", () => {
    const onConfirm = vi.fn();
    render(<PrefilledFormReview fields={[selectField]} onConfirm={onConfirm} onCancel={vi.fn()} isConfirming={false} />);

    fireEvent.change(screen.getByLabelText(/type de poste/i), { target: { value: "Stage" } });
    fireEvent.click(screen.getByRole("button", { name: /envoyer la candidature/i }));

    expect(onConfirm).toHaveBeenCalledWith([{ ...selectField, value: "Stage" }]);
  });

  it("marks an empty required field as à compléter", () => {
    const emptyRequired: FormField = { ...selectField, name: "visa_status", label: "Statut visa", value: null, is_custom: true };
    render(<PrefilledFormReview fields={[emptyRequired]} onConfirm={vi.fn()} onCancel={vi.fn()} isConfirming={false} />);
    expect(screen.getByText(/à compléter/i)).toBeInTheDocument();
  });

  it("does not mark a required field that already has a value as à compléter", () => {
    render(<PrefilledFormReview fields={[selectField]} onConfirm={vi.fn()} onCancel={vi.fn()} isConfirming={false} />);
    expect(screen.queryByText(/à compléter/i)).not.toBeInTheDocument();
  });

  it("does not mark a non-required empty field as à compléter", () => {
    const optionalEmpty: FormField = { ...selectField, required: false, value: null };
    render(<PrefilledFormReview fields={[optionalEmpty]} onConfirm={vi.fn()} onCancel={vi.fn()} isConfirming={false} />);
    expect(screen.queryByText(/à compléter/i)).not.toBeInTheDocument();
  });
});
