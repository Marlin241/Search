import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { RequireAuth } from "./RequireAuth";

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

describe("RequireAuth", () => {
  it("redirects to /login when there is no token and loading is finished", async () => {
    useAuthMock.mockReturnValue({ token: null, isLoading: false });
    render(
      <RequireAuth>
        <p>secret</p>
      </RequireAuth>
    );
    await waitFor(() => expect(replaceMock).toHaveBeenCalledWith("/login"));
    expect(screen.queryByText("secret")).not.toBeInTheDocument();
  });

  it("renders children when a token is present", () => {
    useAuthMock.mockReturnValue({ token: "abc", isLoading: false });
    render(
      <RequireAuth>
        <p>secret</p>
      </RequireAuth>
    );
    expect(screen.getByText("secret")).toBeInTheDocument();
    expect(replaceMock).not.toHaveBeenCalled();
  });

  it("renders nothing while loading", () => {
    useAuthMock.mockReturnValue({ token: null, isLoading: true });
    render(
      <RequireAuth>
        <p>secret</p>
      </RequireAuth>
    );
    expect(screen.queryByText("secret")).not.toBeInTheDocument();
    expect(replaceMock).not.toHaveBeenCalled();
  });
});
