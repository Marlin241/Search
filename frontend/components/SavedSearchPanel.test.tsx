import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { SavedSearchPanel } from "./SavedSearchPanel";
import * as api from "@/lib/api";
import { EMPTY_SEARCH_CRITERIA_FORM_VALUE } from "./SearchCriteriaForm";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    getSavedSearch: vi.fn(),
    saveSavedSearch: vi.fn(),
    ApiError: actual.ApiError,
  };
});

beforeEach(() => {
  vi.mocked(api.getSavedSearch).mockReset();
  vi.mocked(api.saveSavedSearch).mockReset();
});

describe("SavedSearchPanel", () => {
  it("shows 'Sauvegarder' when no saved search exists yet", async () => {
    vi.mocked(api.getSavedSearch).mockResolvedValue(null);
    render(
      <SavedSearchPanel
        token="tok123"
        criteria={{ ...EMPTY_SEARCH_CRITERIA_FORM_VALUE, keywords: "python" }}
      />
    );
    await waitFor(() => expect(api.getSavedSearch).toHaveBeenCalled());
    expect(screen.getByText("Sauvegarder cette recherche")).toBeInTheDocument();
    expect(screen.queryByText("Désactiver")).not.toBeInTheDocument();
  });

  it("pre-fills the timezone and shows the toggle when a saved search exists", async () => {
    vi.mocked(api.getSavedSearch).mockResolvedValue({
      keywords: "python",
      location: null,
      contract_type: null,
      remote: null,
      exclude_keywords: [],
      timezone: "America/New_York",
      enabled: true,
    });
    render(
      <SavedSearchPanel
        token="tok123"
        criteria={{ ...EMPTY_SEARCH_CRITERIA_FORM_VALUE, keywords: "python" }}
      />
    );
    await waitFor(() => expect(screen.getByText("Désactiver")).toBeInTheDocument());
    expect(screen.getByDisplayValue("America/New_York")).toBeInTheDocument();
  });

  it("calls saveSavedSearch with enabled:true when saving", async () => {
    vi.mocked(api.getSavedSearch).mockResolvedValue(null);
    vi.mocked(api.saveSavedSearch).mockResolvedValue({
      keywords: "python",
      location: null,
      contract_type: null,
      remote: null,
      exclude_keywords: [],
      timezone: "Europe/Paris",
      enabled: true,
    });
    render(
      <SavedSearchPanel
        token="tok123"
        criteria={{ ...EMPTY_SEARCH_CRITERIA_FORM_VALUE, keywords: "python" }}
      />
    );
    await waitFor(() => expect(api.getSavedSearch).toHaveBeenCalled());
    fireEvent.click(screen.getByText("Sauvegarder cette recherche"));
    await waitFor(() => expect(api.saveSavedSearch).toHaveBeenCalled());
    expect(vi.mocked(api.saveSavedSearch).mock.calls[0][1]).toMatchObject({
      keywords: "python",
      enabled: true,
    });
  });
});
