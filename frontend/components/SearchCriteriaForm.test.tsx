import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import {
  SearchCriteriaForm,
  EMPTY_SEARCH_CRITERIA_FORM_VALUE,
  toSearchCriteria,
} from "./SearchCriteriaForm";

describe("SearchCriteriaForm", () => {
  it("calls onChange when the keywords field is edited", () => {
    const onChange = vi.fn();
    render(
      <SearchCriteriaForm value={EMPTY_SEARCH_CRITERIA_FORM_VALUE} onChange={onChange} onSearch={vi.fn()} isSearching={false} />
    );
    fireEvent.change(screen.getByLabelText("Mots-clés", { exact: true }), { target: { value: "python" } });
    expect(onChange).toHaveBeenCalledWith({ ...EMPTY_SEARCH_CRITERIA_FORM_VALUE, keywords: "python" });
  });

  it("calls onSearch when the search button is clicked", () => {
    const onSearch = vi.fn();
    render(
      <SearchCriteriaForm value={{ ...EMPTY_SEARCH_CRITERIA_FORM_VALUE, keywords: "python" }} onChange={vi.fn()} onSearch={onSearch} isSearching={false} />
    );
    fireEvent.click(screen.getByRole("button", { name: /rechercher/i }));
    expect(onSearch).toHaveBeenCalled();
  });

  it("disables the search button while searching", () => {
    render(
      <SearchCriteriaForm value={EMPTY_SEARCH_CRITERIA_FORM_VALUE} onChange={vi.fn()} onSearch={vi.fn()} isSearching={true} />
    );
    expect(screen.getByRole("button", { name: /recherche en cours/i })).toBeDisabled();
  });
});

describe("toSearchCriteria", () => {
  it("splits comma-separated fields into trimmed arrays", () => {
    const result = toSearchCriteria({
      ...EMPTY_SEARCH_CRITERIA_FORM_VALUE,
      keywords: "python",
      excludeKeywords: "stage, junior",
      followedCompanies: "acme, globex",
    });
    expect(result.exclude_keywords).toEqual(["stage", "junior"]);
    expect(result.followed_companies).toEqual(["acme", "globex"]);
  });

  it("omits empty optional fields", () => {
    const result = toSearchCriteria(EMPTY_SEARCH_CRITERIA_FORM_VALUE);
    expect(result.location).toBeUndefined();
    expect(result.contract_type).toBeUndefined();
  });
});
