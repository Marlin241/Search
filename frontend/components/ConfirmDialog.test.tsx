import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { ConfirmDialog } from "./ConfirmDialog";

describe("ConfirmDialog", () => {
  it("renders the message", () => {
    render(<ConfirmDialog message="Supprimer ?" onConfirm={vi.fn()} onCancel={vi.fn()} />);
    expect(screen.getByText("Supprimer ?")).toBeInTheDocument();
  });

  it("calls onCancel when Annuler is clicked", () => {
    const onCancel = vi.fn();
    render(<ConfirmDialog message="Supprimer ?" onConfirm={vi.fn()} onCancel={onCancel} />);
    fireEvent.click(screen.getByText("Annuler"));
    expect(onCancel).toHaveBeenCalled();
  });

  it("calls onConfirm when Supprimer is clicked", () => {
    const onConfirm = vi.fn();
    render(<ConfirmDialog message="Supprimer ?" onConfirm={onConfirm} onCancel={vi.fn()} />);
    fireEvent.click(screen.getByText("Supprimer"));
    expect(onConfirm).toHaveBeenCalled();
  });
});
