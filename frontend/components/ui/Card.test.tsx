import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { Card } from "./Card";

describe("Card", () => {
  it("renders its children", () => {
    render(<Card>Contenu</Card>);
    expect(screen.getByText("Contenu")).toBeInTheDocument();
  });

  it("applies the default surface classes", () => {
    render(<Card data-testid="card">Contenu</Card>);
    expect(screen.getByTestId("card").className).toContain("rounded-3xl");
  });

  it("merges a custom className with the defaults", () => {
    render(
      <Card data-testid="card" className="p-4">
        Contenu
      </Card>
    );
    const className = screen.getByTestId("card").className;
    expect(className).toContain("rounded-3xl");
    expect(className).toContain("p-4");
  });
});
