import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { ErrorBanner } from "./ErrorBanner";

describe("ErrorBanner", () => {
  it("renders the message as an alert", () => {
    render(<ErrorBanner content={{ message: "Une erreur est survenue.", variant: "error" }} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Une erreur est survenue.");
  });

  it("applies warning styling for the warning variant", () => {
    render(<ErrorBanner content={{ message: "Limite atteinte.", variant: "warning" }} />);
    expect(screen.getByRole("alert").className).toContain("orange");
  });
});
