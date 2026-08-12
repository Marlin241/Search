import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { AppShell } from "./AppShell";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn() }),
  usePathname: () => "/diagnostic",
}));

const useAuthMock = vi.fn();
vi.mock("@/context/AuthContext", () => ({
  useAuth: () => useAuthMock(),
}));

beforeEach(() => {
  useAuthMock.mockReset();
});

describe("AppShell", () => {
  it("renders children without the sidebar when logged out", () => {
    useAuthMock.mockReturnValue({ user: null, logout: vi.fn() });
    render(
      <AppShell>
        <p>Page content</p>
      </AppShell>
    );
    expect(screen.getByText("Page content")).toBeInTheDocument();
    expect(screen.queryByText("Diagnostic ATS")).not.toBeInTheDocument();
  });

  it("renders the sidebar alongside children when logged in", () => {
    useAuthMock.mockReturnValue({ user: { id: 1, email: "jane@example.com" }, logout: vi.fn() });
    render(
      <AppShell>
        <p>Page content</p>
      </AppShell>
    );
    expect(screen.getByText("Page content")).toBeInTheDocument();
    expect(screen.getByText("Diagnostic ATS")).toBeInTheDocument();
    expect(screen.getByText("jane@example.com")).toBeInTheDocument();
  });
});
