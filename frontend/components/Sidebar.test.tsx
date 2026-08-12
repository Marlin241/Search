import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { Sidebar } from "./Sidebar";

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

describe("Sidebar", () => {
  it("shows only the brand when logged out", () => {
    useAuthMock.mockReturnValue({ user: null, logout: logoutMock });
    render(<Sidebar />);
    expect(screen.getByText("Diagnostic ATS")).toBeInTheDocument();
    expect(screen.queryByText("Historique")).not.toBeInTheDocument();
  });

  it("shows nav links, email, and logs out when logged in", () => {
    useAuthMock.mockReturnValue({ user: { id: 1, email: "jane@example.com" }, logout: logoutMock });
    render(<Sidebar />);
    expect(screen.getByText("Historique")).toBeInTheDocument();
    expect(screen.getByText("Candidatures")).toBeInTheDocument();
    expect(screen.getByText("Profil")).toBeInTheDocument();
    expect(screen.getByText("jane@example.com")).toBeInTheDocument();

    fireEvent.click(screen.getByText("Se déconnecter"));
    expect(logoutMock).toHaveBeenCalled();
    expect(replaceMock).toHaveBeenCalledWith("/login");
  });
});
