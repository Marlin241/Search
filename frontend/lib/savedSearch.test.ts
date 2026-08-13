import { describe, expect, it, vi, beforeEach } from "vitest";
import { getSavedSearch, saveSavedSearch, ApiError } from "./api";

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response;
}

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn());
});

describe("getSavedSearch", () => {
  it("returns null when the backend responds 404", async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse({ detail: "not found" }, 404));
    const result = await getSavedSearch("tok123");
    expect(result).toBeNull();
  });

  it("returns the saved search when found", async () => {
    const saved = {
      keywords: "python",
      location: null,
      contract_type: null,
      remote: null,
      exclude_keywords: [],
      timezone: "Europe/Paris",
      enabled: true,
    };
    vi.mocked(fetch).mockResolvedValue(jsonResponse(saved));
    const result = await getSavedSearch("tok123");
    expect(result).toEqual(saved);
  });

  it("rethrows non-404 errors", async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse({ detail: "boom" }, 500));
    await expect(getSavedSearch("tok123")).rejects.toBeInstanceOf(ApiError);
  });
});

describe("saveSavedSearch", () => {
  it("PUTs the payload and returns the saved search", async () => {
    const saved = {
      keywords: "python",
      location: null,
      contract_type: null,
      remote: null,
      exclude_keywords: [],
      timezone: "Europe/Paris",
      enabled: true,
    };
    vi.mocked(fetch).mockResolvedValue(jsonResponse(saved));
    const result = await saveSavedSearch("tok123", {
      keywords: "python",
      exclude_keywords: [],
      timezone: "Europe/Paris",
      enabled: true,
    });
    expect(result).toEqual(saved);
    const [, init] = vi.mocked(fetch).mock.calls[0];
    expect(init?.method).toBe("PUT");
  });
});
