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
    expect(screen.getByText("Envoyée").className).toContain("bg-slate-100");
  });

  it("applies the emerald variant class", () => {
    render(<Badge variant="emerald">Envoyée</Badge>);
    expect(screen.getByText("Envoyée").className).toContain("emerald");
  });

  it("applies the red variant class", () => {
    render(<Badge variant="red">Échec</Badge>);
    expect(screen.getByText("Échec").className).toContain("red");
  });
});
