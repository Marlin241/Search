import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { PrefilledFormReview } from "./PrefilledFormReview";
import type { FormField } from "@/lib/types";

const fields: FormField[] = [
  { name: "first_name", label: "First name", field_type: "text", required: true, options: null, value: "Jane", is_custom: false },
  { name: "custom_why", label: "Why this role?", field_type: "textarea", required: false, options: null, value: "Réponse générée.", is_custom: true },
];

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
});
