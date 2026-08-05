import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { AuthForm } from "./AuthForm";
import { ApiError } from "@/lib/api";

describe("AuthForm", () => {
  it("renders the login heading and submit label by default", () => {
    render(<AuthForm mode="login" onModeChange={vi.fn()} onSubmit={vi.fn()} />);
    expect(screen.getByText("Connexion")).toBeInTheDocument();
    expect(screen.getByText("Se connecter")).toBeInTheDocument();
  });

  it("renders the register heading and submit label in register mode", () => {
    render(<AuthForm mode="register" onModeChange={vi.fn()} onSubmit={vi.fn()} />);
    expect(screen.getByText("Inscription")).toBeInTheDocument();
    expect(screen.getByText("Créer mon compte")).toBeInTheDocument();
  });

  it("calls onModeChange when the toggle link is clicked", () => {
    const onModeChange = vi.fn();
    render(<AuthForm mode="login" onModeChange={onModeChange} onSubmit={vi.fn()} />);
    fireEvent.click(screen.getByText("Pas de compte ? S'inscrire"));
    expect(onModeChange).toHaveBeenCalledWith("register");
  });

  it("submits the typed email and password", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(<AuthForm mode="login" onModeChange={vi.fn()} onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "jane@example.com" } });
    fireEvent.change(screen.getByLabelText("Mot de passe"), { target: { value: "s3cret!" } });
    fireEvent.click(screen.getByText("Se connecter"));

    await waitFor(() => expect(onSubmit).toHaveBeenCalledWith("jane@example.com", "s3cret!"));
  });

  it("shows the error under the email field for a 409 conflict", async () => {
    const onSubmit = vi.fn().mockRejectedValue(new ApiError(409, "Cet email est déjà utilisé."));
    render(<AuthForm mode="register" onModeChange={vi.fn()} onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "dup@example.com" } });
    fireEvent.change(screen.getByLabelText("Mot de passe"), { target: { value: "pw" } });
    fireEvent.click(screen.getByText("Créer mon compte"));

    await waitFor(() => expect(screen.getByText("Cet email est déjà utilisé.")).toBeInTheDocument());
  });

  it("shows a form-level banner for other errors", async () => {
    const onSubmit = vi.fn().mockRejectedValue(new ApiError(401, "Email ou mot de passe incorrect."));
    render(<AuthForm mode="login" onModeChange={vi.fn()} onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "jane@example.com" } });
    fireEvent.change(screen.getByLabelText("Mot de passe"), { target: { value: "wrong" } });
    fireEvent.click(screen.getByText("Se connecter"));

    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Email ou mot de passe incorrect."));
  });
});
