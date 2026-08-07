import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { CandidateProfileForm, EMPTY_CANDIDATE_PROFILE_FORM_VALUE } from "./CandidateProfileForm";

describe("CandidateProfileForm", () => {
  it("renders the current value in each field", () => {
    render(
      <CandidateProfileForm
        value={{ ...EMPTY_CANDIDATE_PROFILE_FORM_VALUE, full_name: "Jane Doe" }}
        onChange={vi.fn()}
        onSubmit={vi.fn()}
        isSubmitting={false}
      />
    );
    expect(screen.getByLabelText(/nom complet/i)).toHaveValue("Jane Doe");
  });

  it("calls onChange when a field is edited", () => {
    const onChange = vi.fn();
    render(
      <CandidateProfileForm value={EMPTY_CANDIDATE_PROFILE_FORM_VALUE} onChange={onChange} onSubmit={vi.fn()} isSubmitting={false} />
    );
    fireEvent.change(screen.getByLabelText(/nom complet/i), { target: { value: "Jane Doe" } });
    expect(onChange).toHaveBeenCalledWith({ ...EMPTY_CANDIDATE_PROFILE_FORM_VALUE, full_name: "Jane Doe" });
  });

  it("calls onSubmit when the save button is clicked", () => {
    const onSubmit = vi.fn();
    render(
      <CandidateProfileForm value={EMPTY_CANDIDATE_PROFILE_FORM_VALUE} onChange={vi.fn()} onSubmit={onSubmit} isSubmitting={false} />
    );
    fireEvent.click(screen.getByRole("button", { name: /enregistrer/i }));
    expect(onSubmit).toHaveBeenCalled();
  });

  it("disables the save button while submitting", () => {
    render(
      <CandidateProfileForm value={EMPTY_CANDIDATE_PROFILE_FORM_VALUE} onChange={vi.fn()} onSubmit={vi.fn()} isSubmitting={true} />
    );
    expect(screen.getByRole("button", { name: /enregistrement/i })).toBeDisabled();
  });
});
