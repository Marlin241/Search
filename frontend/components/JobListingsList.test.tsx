import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { JobListingsList } from "./JobListingsList";
import type { JobListing } from "@/lib/types";

const listings: JobListing[] = [
  { title: "Développeur Python", company: "Acme", location: "Paris", snippet: "...", url: "https://example.com/1", source: "adzuna", ats_type: null },
  { title: "Chef de projet", company: "Globex", location: "Lyon", snippet: "...", url: "https://example.com/2", source: "france_travail", ats_type: null },
];

describe("JobListingsList", () => {
  it("renders every listing", () => {
    render(<JobListingsList listings={listings} unavailableSources={[]} onCreateApplications={vi.fn()} isCreating={false} />);
    expect(screen.getByText("Développeur Python")).toBeInTheDocument();
    expect(screen.getByText("Chef de projet")).toBeInTheDocument();
  });

  it("shows a warning for unavailable sources", () => {
    render(<JobListingsList listings={listings} unavailableSources={["france_travail"]} onCreateApplications={vi.fn()} isCreating={false} />);
    expect(screen.getByText(/sources indisponibles.*france_travail/i)).toBeInTheDocument();
  });

  it("disables the create-applications button until at least one listing is checked", () => {
    render(<JobListingsList listings={listings} unavailableSources={[]} onCreateApplications={vi.fn()} isCreating={false} />);
    expect(screen.getByRole("button", { name: /lancer le diagnostic/i })).toBeDisabled();
  });

  it("calls onCreateApplications with only the checked listings", () => {
    const onCreateApplications = vi.fn();
    render(<JobListingsList listings={listings} unavailableSources={[]} onCreateApplications={onCreateApplications} isCreating={false} />);

    fireEvent.click(screen.getByLabelText("Développeur Python"));
    fireEvent.click(screen.getByRole("button", { name: /lancer le diagnostic/i }));

    expect(onCreateApplications).toHaveBeenCalledWith([listings[0]]);
  });

  it("disables the button while creating", () => {
    render(<JobListingsList listings={listings} unavailableSources={[]} onCreateApplications={vi.fn()} isCreating={true} />);
    fireEvent.click(screen.getByLabelText("Développeur Python"));
    expect(screen.getByRole("button", { name: /lancement en cours/i })).toBeDisabled();
  });
});
