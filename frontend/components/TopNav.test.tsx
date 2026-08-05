import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { TopNav } from "./TopNav";

const replaceMock = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: replaceMock }),
  usePathname: () => "/diagnostic",
}));

const logoutMock = vi.fn();
const useAuthMock = vi.fn();
vi.mock("@/context/AuthContext", () => ({
  useAuth: () => useAuthMock(),
}));

beforeEach(() => {
  replaceMock.mockReset();
  logoutMock.mockReset();
  useAuthMock.mockReset();
});

describe("TopNav", () => {
  it("shows only the logo when logged out", () => {
    useAuthMock.mockReturnValue({ user: null, logout: logoutMock });
    render(<TopNav />);
    expect(screen.getByText("📄 Diagnostic ATS")).toBeInTheDocument();
    expect(screen.queryByText("Historique")).not.toBeInTheDocument();
  });

  it("shows nav links, email, and logs out when logged in", () => {
    useAuthMock.mockReturnValue({ user: { id: 1, email: "jane@example.com" }, logout: logoutMock });
    render(<TopNav />);
    expect(screen.getByText("Historique")).toBeInTheDocument();
    expect(screen.getByText("jane@example.com")).toBeInTheDocument();

    fireEvent.click(screen.getByText("Se déconnecter"));
    expect(logoutMock).toHaveBeenCalled();
    expect(replaceMock).toHaveBeenCalledWith("/login");
  });
});
