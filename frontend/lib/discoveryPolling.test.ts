import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { pollJobSearchDiscovery } from "./discoveryPolling";
import * as api from "./api";
import type { JobListing } from "./types";

vi.mock("./api", () => ({
  fetchJobSearchDiscovery: vi.fn(),
}));

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

function listing(url: string): JobListing {
  return {
    title: "Ingénieur backend",
    company: "Acme",
    location: null,
    snippet: "",
    url,
    source: "greenhouse",
    ats_type: "greenhouse",
  };
}

describe("pollJobSearchDiscovery", () => {
  it("calls onNewListings for each batch and onDone when finished", async () => {
    vi.mocked(api.fetchJobSearchDiscovery)
      .mockResolvedValueOnce({ done: false, new_listings: [listing("https://example.com/a")] })
      .mockResolvedValueOnce({ done: true, new_listings: [listing("https://example.com/b")] });

    const onNewListings = vi.fn();
    const onDone = vi.fn();

    pollJobSearchDiscovery("tok", "search-1", onNewListings, onDone, 1000);

    await vi.advanceTimersByTimeAsync(1000);
    expect(onNewListings).toHaveBeenNthCalledWith(1, [listing("https://example.com/a")]);
    expect(onDone).not.toHaveBeenCalled();

    await vi.advanceTimersByTimeAsync(1000);
    expect(onNewListings).toHaveBeenNthCalledWith(2, [listing("https://example.com/b")]);
    expect(onDone).toHaveBeenCalledTimes(1);

    await vi.advanceTimersByTimeAsync(5000);
    expect(api.fetchJobSearchDiscovery).toHaveBeenCalledTimes(2);
  });

  it("stops polling and calls onDone when a request fails", async () => {
    vi.mocked(api.fetchJobSearchDiscovery).mockRejectedValue(new Error("network error"));

    const onNewListings = vi.fn();
    const onDone = vi.fn();

    pollJobSearchDiscovery("tok", "search-1", onNewListings, onDone, 1000);

    await vi.advanceTimersByTimeAsync(1000);
    expect(onDone).toHaveBeenCalledTimes(1);
    expect(onNewListings).not.toHaveBeenCalled();

    await vi.advanceTimersByTimeAsync(5000);
    expect(api.fetchJobSearchDiscovery).toHaveBeenCalledTimes(1);
  });

  it("returns a cancel function that stops further polling", async () => {
    vi.mocked(api.fetchJobSearchDiscovery).mockResolvedValue({ done: false, new_listings: [] });

    const cancel = pollJobSearchDiscovery("tok", "search-1", vi.fn(), vi.fn(), 1000);
    cancel();

    await vi.advanceTimersByTimeAsync(5000);
    expect(api.fetchJobSearchDiscovery).not.toHaveBeenCalled();
  });
});
