import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { Badge } from "./Badge";

describe("Badge", () => {
  it("renders its children", () => {
    render(<Badge>Envoyée</Badge>);
    expect(screen.getByText("Envoyée")).toBeInTheDocument();
  });

  it("defaults to the neutral variant", () => {
    render(<Badge>Envoyée</Badge>);
    expect(screen.getByText("Envoyée").className).toContain("bg-surface-2");
  });

  it("applies the success variant class", () => {
    render(<Badge variant="success">Envoyée</Badge>);
    expect(screen.getByText("Envoyée").className).toContain("success");
  });

  it("applies the attention variant class", () => {
    render(<Badge variant="attention">Échec</Badge>);
    expect(screen.getByText("Échec").className).toContain("attention");
  });
});
