import type { CandidateProfile, CandidateProfileInput, DiagnosticReport, PersonalizedDocument, User, SearchCriteria, JobSearchResult } from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;

  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
  }
}

async function parseErrorDetail(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body.detail === "string") return body.detail;
  } catch {
    // response body wasn't JSON — fall through to the generic message
  }
  return "Une erreur est survenue.";
}

async function request<T>(path: string, init: RequestInit, token?: string | null): Promise<T> {
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers });
  } catch {
    throw new ApiError(0, "Impossible de contacter le serveur.");
  }

  if (!response.ok) {
    throw new ApiError(response.status, await parseErrorDetail(response));
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export function register(email: string, password: string): Promise<User> {
  return request<User>("/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
}

export function login(email: string, password: string): Promise<{ access_token: string; token_type: string }> {
  const form = new URLSearchParams();
  form.set("username", email);
  form.set("password", password);
  return request("/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: form.toString(),
  });
}

export function fetchMe(token: string): Promise<User> {
  return request<User>("/auth/me", { method: "GET" }, token);
}

export function createDiagnostic(
  token: string,
  cvFile: File,
  offer: { text?: string; url?: string }
): Promise<DiagnosticReport> {
  const formData = new FormData();
  formData.append("cv_file", cvFile);
  if (offer.text) formData.append("offer_text", offer.text);
  if (offer.url) formData.append("offer_url", offer.url);
  return request<DiagnosticReport>("/diagnostics", { method: "POST", body: formData }, token);
}

export function listDiagnostics(token: string): Promise<DiagnosticReport[]> {
  return request<DiagnosticReport[]>("/diagnostics", { method: "GET" }, token);
}

export function deleteAllDiagnostics(token: string): Promise<void> {
  return request<void>("/diagnostics", { method: "DELETE" }, token);
}

async function requestBlob(path: string, token: string): Promise<Blob> {
  const headers = new Headers();
  headers.set("Authorization", `Bearer ${token}`);

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, { headers });
  } catch {
    throw new ApiError(0, "Impossible de contacter le serveur.");
  }
  if (!response.ok) {
    throw new ApiError(response.status, await parseErrorDetail(response));
  }
  return response.blob();
}

export function generateCv(token: string, diagnosticId: number): Promise<PersonalizedDocument> {
  return request<PersonalizedDocument>(`/diagnostics/${diagnosticId}/cv`, { method: "POST" }, token);
}

export function generateLetter(token: string, diagnosticId: number): Promise<PersonalizedDocument> {
  return request<PersonalizedDocument>(`/diagnostics/${diagnosticId}/lettre`, { method: "POST" }, token);
}

export function downloadCv(token: string, diagnosticId: number): Promise<Blob> {
  return requestBlob(`/diagnostics/${diagnosticId}/cv`, token);
}

export function downloadLetter(token: string, diagnosticId: number): Promise<Blob> {
  return requestBlob(`/diagnostics/${diagnosticId}/lettre`, token);
}

export function getCandidateProfile(token: string): Promise<CandidateProfile> {
  return request<CandidateProfile>("/profile", { method: "GET" }, token);
}

export function updateCandidateProfile(token: string, payload: CandidateProfileInput): Promise<CandidateProfile> {
  return request<CandidateProfile>(
    "/profile",
    { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) },
    token
  );
}

export function uploadReferenceCv(token: string, file: File): Promise<CandidateProfile> {
  const formData = new FormData();
  formData.append("cv_file", file);
  return request<CandidateProfile>("/profile/cv", { method: "POST", body: formData }, token);
}

export function searchJobs(token: string, criteria: SearchCriteria): Promise<JobSearchResult> {
  return request<JobSearchResult>(
    "/job-search/search",
    { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(criteria) },
    token
  );
}
