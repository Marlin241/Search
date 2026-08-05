import { render, screen, waitFor, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { AuthProvider, useAuth } from "./AuthContext";
import * as api from "@/lib/api";
import { ApiError } from "@/lib/api";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    login: vi.fn(),
    register: vi.fn(),
    fetchMe: vi.fn(),
    ApiError: actual.ApiError,
  };
});

function Probe() {
  const { user, token, isLoading, login, logout } = useAuth();
  return (
    <div>
      <span data-testid="loading">{String(isLoading)}</span>
      <span data-testid="token">{token ?? "none"}</span>
      <span data-testid="email">{user?.email ?? "none"}</span>
      <button onClick={() => login("jane@example.com", "pw")}>login</button>
      <button onClick={() => logout()}>logout</button>
    </div>
  );
}

beforeEach(() => {
  localStorage.clear();
  vi.mocked(api.login).mockReset();
  vi.mocked(api.fetchMe).mockReset();
});

describe("AuthProvider", () => {
  it("starts with no token when localStorage is empty", async () => {
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>
    );
    await waitFor(() => expect(screen.getByTestId("loading").textContent).toBe("false"));
    expect(screen.getByTestId("token").textContent).toBe("none");
  });

  it("restores the user from a token already in localStorage", async () => {
    localStorage.setItem("ats_diagnostic_token", "existing-token");
    vi.mocked(api.fetchMe).mockResolvedValue({ id: 2, email: "restored@example.com" });

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>
    );

    await waitFor(() => expect(screen.getByTestId("email").textContent).toBe("restored@example.com"));
    expect(api.fetchMe).toHaveBeenCalledWith("existing-token");
  });

  it("clears an invalid stored token", async () => {
    localStorage.setItem("ats_diagnostic_token", "bad-token");
    vi.mocked(api.fetchMe).mockRejectedValue(new ApiError(401, "Unauthorized"));

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>
    );

    await waitFor(() => expect(screen.getByTestId("loading").textContent).toBe("false"));
    expect(screen.getByTestId("token").textContent).toBe("none");
    expect(localStorage.getItem("ats_diagnostic_token")).toBeNull();
  });

  it("keeps a stored token on a non-401 restoration failure", async () => {
    localStorage.setItem("ats_diagnostic_token", "existing-token");
    vi.mocked(api.fetchMe).mockRejectedValue(new ApiError(0, "Impossible de contacter le serveur."));

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>
    );

    await waitFor(() => expect(screen.getByTestId("loading").textContent).toBe("false"));
    expect(screen.getByTestId("token").textContent).toBe("none");
    expect(localStorage.getItem("ats_diagnostic_token")).toBe("existing-token");
  });

  it("login stores the token and exposes the user", async () => {
    vi.mocked(api.login).mockResolvedValue({ access_token: "abc123", token_type: "bearer" });
    vi.mocked(api.fetchMe).mockResolvedValue({ id: 1, email: "jane@example.com" });

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>
    );
    await waitFor(() => expect(screen.getByTestId("loading").textContent).toBe("false"));

    await act(async () => {
      screen.getByText("login").click();
    });

    await waitFor(() => expect(screen.getByTestId("token").textContent).toBe("abc123"));
    expect(screen.getByTestId("email").textContent).toBe("jane@example.com");
    expect(localStorage.getItem("ats_diagnostic_token")).toBe("abc123");
  });

  it("logout clears the token", async () => {
    vi.mocked(api.login).mockResolvedValue({ access_token: "abc123", token_type: "bearer" });
    vi.mocked(api.fetchMe).mockResolvedValue({ id: 1, email: "jane@example.com" });

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>
    );
    await waitFor(() => expect(screen.getByTestId("loading").textContent).toBe("false"));
    await act(async () => {
      screen.getByText("login").click();
    });
    await waitFor(() => expect(screen.getByTestId("token").textContent).toBe("abc123"));

    await act(async () => {
      screen.getByText("logout").click();
    });

    expect(screen.getByTestId("token").textContent).toBe("none");
    expect(localStorage.getItem("ats_diagnostic_token")).toBeNull();
  });
});
