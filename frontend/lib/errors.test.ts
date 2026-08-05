import { describe, it, expect } from "vitest";
import { toBannerContent, isSessionExpired } from "./errors";
import { ApiError } from "./api";

describe("toBannerContent", () => {
  it("maps a 429 rate-limit error to the warning variant", () => {
    const content = toBannerContent(new ApiError(429, "Limite atteinte, réessayez plus tard."));
    expect(content).toEqual({ message: "Limite atteinte, réessayez plus tard.", variant: "warning" });
  });

  it("maps a 422 error to the error variant with the backend message", () => {
    const content = toBannerContent(new ApiError(422, "Ce CV semble être une image scannée."));
    expect(content).toEqual({ message: "Ce CV semble être une image scannée.", variant: "error" });
  });

  it("maps a network failure (status 0) to a generic error message", () => {
    const content = toBannerContent(new ApiError(0, "Impossible de contacter le serveur."));
    expect(content).toEqual({ message: "Impossible de contacter le serveur.", variant: "error" });
  });

  it("maps a non-ApiError to a generic error message", () => {
    const content = toBannerContent(new Error("boom"));
    expect(content).toEqual({ message: "Une erreur est survenue.", variant: "error" });
  });
});

describe("isSessionExpired", () => {
  it("is true for a 401 ApiError", () => {
    expect(isSessionExpired(new ApiError(401, "Impossible de valider les identifiants."))).toBe(true);
  });

  it("is false for other ApiErrors", () => {
    expect(isSessionExpired(new ApiError(422, "CV invalide."))).toBe(false);
  });

  it("is false for a non-ApiError", () => {
    expect(isSessionExpired(new Error("boom"))).toBe(false);
  });
});
