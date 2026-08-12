import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { Button } from "./Button";

describe("Button", () => {
  it("renders its children", () => {
    render(<Button>Valider</Button>);
    expect(screen.getByRole("button", { name: "Valider" })).toBeInTheDocument();
  });

  it("calls onClick when clicked", () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Valider</Button>);
    fireEvent.click(screen.getByRole("button", { name: "Valider" }));
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it("is disabled when the disabled prop is set", () => {
    render(<Button disabled>Valider</Button>);
    expect(screen.getByRole("button", { name: "Valider" })).toBeDisabled();
  });

  it("disables the button and blocks onClick when isLoading is true", () => {
    const onClick = vi.fn();
    render(
      <Button isLoading onClick={onClick}>
        Envoi en cours...
      </Button>
    );
    const button = screen.getByRole("button", { name: "Envoi en cours..." });
    expect(button).toBeDisabled();
    fireEvent.click(button);
    expect(onClick).not.toHaveBeenCalled();
  });

  it("applies the danger variant class", () => {
    render(<Button variant="danger">Supprimer</Button>);
    expect(screen.getByRole("button", { name: "Supprimer" }).className).toContain("bg-red-600");
  });
});
