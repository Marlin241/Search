import { describe, it, expect } from "vitest";
import { sourceLabel, isLikelyRemote } from "./jobListingPresentation";

describe("sourceLabel", () => {
  it("maps known source slugs to their friendly French label", () => {
    expect(sourceLabel("france_travail")).toBe("France Travail");
    expect(sourceLabel("la_bonne_alternance")).toBe("La Bonne Alternance");
  });

  it("title-cases unknown source slugs as a fallback", () => {
    expect(sourceLabel("some_new_source")).toBe("Some New Source");
  });
});

describe("isLikelyRemote", () => {
  it("detects remote indicators in the snippet", () => {
    expect(isLikelyRemote({ location: "Paris", snippet: "Poste en télétravail total." })).toBe(true);
  });

  it("detects remote indicators in the location", () => {
    expect(isLikelyRemote({ location: "Remote", snippet: "..." })).toBe(true);
  });

  it("returns false when nothing suggests remote work", () => {
    expect(isLikelyRemote({ location: "Lyon", snippet: "Poste sur site, présentiel requis." })).toBe(false);
  });

  it("handles a null location", () => {
    expect(isLikelyRemote({ location: null, snippet: "Distanciel possible." })).toBe(true);
  });
});
