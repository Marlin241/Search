import { render, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import Home from "./page";

const replaceMock = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: replaceMock }),
}));

const useAuthMock = vi.fn();
vi.mock("@/context/AuthContext", () => ({
  useAuth: () => useAuthMock(),
}));

beforeEach(() => {
  replaceMock.mockReset();
  useAuthMock.mockReset();
});

describe("Home page", () => {
  it("redirects to /diagnostic when authenticated", async () => {
    useAuthMock.mockReturnValue({ token: "abc", isLoading: false });
    render(<Home />);
    await waitFor(() => expect(replaceMock).toHaveBeenCalledWith("/diagnostic"));
  });

  it("redirects to /login when not authenticated", async () => {
    useAuthMock.mockReturnValue({ token: null, isLoading: false });
    render(<Home />);
    await waitFor(() => expect(replaceMock).toHaveBeenCalledWith("/login"));
  });
});
