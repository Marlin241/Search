import { ApiError } from "./api";

export type BannerVariant = "error" | "warning";

export interface BannerContent {
  message: string;
  variant: BannerVariant;
}

export function toBannerContent(error: unknown): BannerContent {
  if (error instanceof ApiError) {
    return { message: error.message, variant: error.status === 429 ? "warning" : "error" };
  }
  return { message: "Une erreur est survenue.", variant: "error" };
}

export function isSessionExpired(error: unknown): boolean {
  return error instanceof ApiError && error.status === 401;
}
