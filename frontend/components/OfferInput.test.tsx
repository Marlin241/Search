import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { OfferInput, EMPTY_OFFER_VALUE } from "./OfferInput";

describe("OfferInput", () => {
  it("shows the text tab by default", () => {
    render(<OfferInput value={EMPTY_OFFER_VALUE} onChange={vi.fn()} />);
    expect(screen.getByPlaceholderText("Collez ici le texte de l'offre d'emploi")).toBeInTheDocument();
  });

  it("switches to the URL tab on click", () => {
    const onChange = vi.fn();
    render(<OfferInput value={EMPTY_OFFER_VALUE} onChange={onChange} />);

    fireEvent.click(screen.getByText("URL de l'offre"));

    expect(onChange).toHaveBeenCalledWith({ ...EMPTY_OFFER_VALUE, mode: "url" });
  });

  it("shows the URL input when mode is url", () => {
    render(<OfferInput value={{ ...EMPTY_OFFER_VALUE, mode: "url" }} onChange={vi.fn()} />);
    expect(screen.getByPlaceholderText("https://...")).toBeInTheDocument();
  });

  it("reports text changes", () => {
    const onChange = vi.fn();
    render(<OfferInput value={EMPTY_OFFER_VALUE} onChange={onChange} />);

    fireEvent.change(screen.getByPlaceholderText("Collez ici le texte de l'offre d'emploi"), {
      target: { value: "Poste de développeur" },
    });

    expect(onChange).toHaveBeenCalledWith({ ...EMPTY_OFFER_VALUE, text: "Poste de développeur" });
  });
});
