import {
  ApiError,
  type ApplicationCreateIn,
  type ApplicationOut,
  type CandidateProfileIn,
  type CandidateProfileOut,
  type CompatibilityDetailOut,
  type ConfirmApplicationIn,
  type CvStyleOptions,
  type CvTemplate,
  type DiagnosticReport,
  type ExtractedPhotoOut,
  type GenerationJobOut,
  type GenerationJobStarted,
  type JobListing,
  type JobSearchDiscoveryResponse,
  type JobSearchResponse,
  type OnboardingProfileIn,
  type PersonalizedDocumentOut,
  type PrefilledFormOut,
  type RewrittenCv,
  type SavedJobIn,
  type SavedJobOut,
  type SavedSearchIn,
  type SavedSearchOut,
  type SearchCriteria,
  type Token,
  type User,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "/api";

/* ─── Global 401 handling ───
 * api.ts is plain fetch code with no access to React context, so the
 * AuthProvider registers a callback here on mount. Any request that comes
 * back 401 (expired/invalid token) triggers a forced logout + redirect,
 * instead of leaving pages silently broken with a stale token. */
type UnauthorizedHandler = () => void;
let onUnauthorized: UnauthorizedHandler | null = null;

export function setUnauthorizedHandler(handler: UnauthorizedHandler | null) {
  onUnauthorized = handler;
}

function handleResponseError(status: number, detail: string): never {
  if (status === 401) onUnauthorized?.();
  throw new ApiError(status, detail);
}

/* ─── Helpers ─── */

async function request<T>(
  path: string,
  options: RequestInit = {},
  token?: string | null
): Promise<T> {
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  if (
    !(options.body instanceof FormData) &&
    !headers["Content-Type"]
  ) {
    headers["Content-Type"] = "application/json";
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  if (!res.ok) {
    let detail = `Erreur ${res.status}`;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      /* ignore parse error */
    }
    handleResponseError(res.status, detail);
  }

  if (res.status === 204) return undefined as T;

  const contentType = res.headers.get("content-type") ?? "";
  if (contentType.includes("application/json")) return res.json();
  return res as unknown as T;
}

/* ─── Auth ─── */

export async function register(
  email: string,
  password: string
): Promise<User> {
  return request<User>("/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export async function login(
  email: string,
  password: string
): Promise<Token> {
  const form = new URLSearchParams();
  form.append("username", email);
  form.append("password", password);
  return request<Token>("/auth/login", {
    method: "POST",
    body: form,
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
  });
}

export async function fetchMe(token: string): Promise<User> {
  return request<User>("/auth/me", {}, token);
}

/* ─── Candidate Profile ─── */

export async function getCandidateProfile(
  token: string
): Promise<CandidateProfileOut> {
  return request<CandidateProfileOut>("/profile", {}, token);
}

export async function updateCandidateProfile(
  token: string,
  data: CandidateProfileIn
): Promise<CandidateProfileOut> {
  return request<CandidateProfileOut>(
    "/profile",
    { method: "PUT", body: JSON.stringify(data) },
    token
  );
}

export async function uploadReferenceCv(
  token: string,
  file: File
): Promise<CandidateProfileOut> {
  const form = new FormData();
  form.append("cv_file", file);
  return request<CandidateProfileOut>(
    "/profile/cv",
    { method: "POST", body: form },
    token
  );
}

export async function deleteProfile(token: string): Promise<void> {
  return request<void>("/profile", { method: "DELETE" }, token);
}

export async function submitOnboarding(
  token: string,
  data: OnboardingProfileIn
): Promise<CandidateProfileOut> {
  return request<CandidateProfileOut>(
    "/profile/onboarding",
    { method: "PUT", body: JSON.stringify(data) },
    token
  );
}

export async function extractCvPhotos(
  token: string,
  file: File
): Promise<ExtractedPhotoOut[]> {
  const form = new FormData();
  form.append("cv_file", file);
  return request<ExtractedPhotoOut[]>(
    "/profile/cv/extract-photos",
    { method: "POST", body: form },
    token
  );
}

export async function uploadManualPhoto(
  token: string,
  file: File
): Promise<ExtractedPhotoOut> {
  const form = new FormData();
  form.append("photo_file", file);
  return request<ExtractedPhotoOut>(
    "/profile/photo/upload",
    { method: "POST", body: form },
    token
  );
}

export async function setProfilePhoto(
  token: string,
  photoKey: string | null
): Promise<CandidateProfileOut> {
  return request<CandidateProfileOut>(
    "/profile/photo",
    { method: "PUT", body: JSON.stringify({ photo_key: photoKey }) },
    token
  );
}

export async function getProfilePhoto(
  token: string,
  previewUrlOrSuffix: string
): Promise<Blob> {
  // Photos are served behind auth (GET /profile/photo/{suffix} requires a
  // Bearer token), so they can't be a plain <img src="..."> - fetch as an
  // authenticated blob and let the caller turn it into an object URL, same
  // pattern as downloadCv/downloadLetter.
  const suffix = previewUrlOrSuffix.startsWith("/profile/photo/")
    ? previewUrlOrSuffix.slice("/profile/photo/".length)
    : previewUrlOrSuffix;
  return requestBlob(`/profile/photo/${suffix}`, token);
}

/* ─── Diagnostics ─── */

export async function createDiagnostic(
  token: string,
  cvFile: File,
  offerText?: string | null,
  offerUrl?: string | null,
  savedJobId?: number | null
): Promise<DiagnosticReport> {
  const form = new FormData();
  form.append("cv_file", cvFile);
  if (offerText) form.append("offer_text", offerText);
  if (offerUrl) form.append("offer_url", offerUrl);
  if (savedJobId != null) form.append("saved_job_id", String(savedJobId));
  return request<DiagnosticReport>(
    "/diagnostics",
    { method: "POST", body: form },
    token
  );
}

export async function listDiagnostics(
  token: string
): Promise<DiagnosticReport[]> {
  return request<DiagnosticReport[]>("/diagnostics", {}, token);
}

export async function deleteAllDiagnostics(
  token: string
): Promise<void> {
  return request<void>(
    "/diagnostics",
    { method: "DELETE" },
    token
  );
}

/* ─── Personalization ─── */

export async function generateCv(
  token: string,
  diagnosticId: number,
  template: CvTemplate = "classic",
  targetLanguage: string = "fr"
): Promise<GenerationJobStarted> {
  const form = new FormData();
  form.append("template", template);
  form.append("target_language", targetLanguage);
  return request<GenerationJobStarted>(
    `/diagnostics/${diagnosticId}/cv`,
    { method: "POST", body: form },
    token
  );
}

export async function getGenerationJob(
  token: string,
  jobId: string
): Promise<GenerationJobOut> {
  return request<GenerationJobOut>(`/generation-jobs/${jobId}`, {}, token);
}

export async function renderCvPreview(
  token: string,
  savedJobId: number,
  payload: { content: RewrittenCv; template: CvTemplate; style: CvStyleOptions }
): Promise<Blob> {
  const res = await fetch(
    `${API_BASE}/saved-jobs/${savedJobId}/cv/render-preview`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(payload),
    }
  );
  if (!res.ok) {
    let detail = `Erreur ${res.status}`;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      /* ignore parse error */
    }
    handleResponseError(res.status, detail);
  }
  return res.blob();
}

export async function generateLetter(
  token: string,
  diagnosticId: number
): Promise<PersonalizedDocumentOut> {
  return request<PersonalizedDocumentOut>(
    `/diagnostics/${diagnosticId}/lettre`,
    { method: "POST" },
    token
  );
}

async function requestBlob(
  path: string,
  token?: string | null
): Promise<Blob> {
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}${path}`, {
    method: "GET",
    headers,
  });

  if (!res.ok) {
    let detail = `Erreur ${res.status}`;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      /* ignore parse error */
    }
    handleResponseError(res.status, detail);
  }

  return res.blob();
}

export async function downloadCv(
  token: string,
  diagnosticId: number
): Promise<Blob> {
  return requestBlob(`/diagnostics/${diagnosticId}/cv`, token);
}

export async function downloadLetter(
  token: string,
  diagnosticId: number
): Promise<Blob> {
  return requestBlob(`/diagnostics/${diagnosticId}/lettre`, token);
}

/* ─── Job Search ─── */

export async function searchJobs(
  token: string,
  criteria: SearchCriteria
): Promise<JobSearchResponse> {
  return request<JobSearchResponse>(
    "/job-search/search",
    { method: "POST", body: JSON.stringify(criteria) },
    token
  );
}

export async function fetchJobSearchDiscovery(
  token: string,
  searchId: string
): Promise<JobSearchDiscoveryResponse> {
  return request<JobSearchDiscoveryResponse>(
    `/job-search/search/${searchId}/discovery`,
    {},
    token
  );
}

export async function getCompatibilityDetail(
  token: string,
  listing: JobListing
): Promise<CompatibilityDetailOut> {
  return request<CompatibilityDetailOut>(
    "/job-search/compatibility-detail",
    { method: "POST", body: JSON.stringify({ listing }) },
    token
  );
}

export async function getSavedSearch(
  token: string
): Promise<SavedSearchOut> {
  return request<SavedSearchOut>(
    "/job-search/saved-search",
    {},
    token
  );
}

export async function saveSavedSearch(
  token: string,
  data: SavedSearchIn
): Promise<SavedSearchOut> {
  return request<SavedSearchOut>(
    "/job-search/saved-search",
    { method: "PUT", body: JSON.stringify(data) },
    token
  );
}

/* ─── Saved Jobs (workspace) ─── */

export async function openSavedJob(
  token: string,
  data: SavedJobIn
): Promise<SavedJobOut> {
  return request<SavedJobOut>(
    "/saved-jobs",
    { method: "POST", body: JSON.stringify(data) },
    token
  );
}

export async function listSavedJobs(token: string): Promise<SavedJobOut[]> {
  return request<SavedJobOut[]>("/saved-jobs", {}, token);
}

export async function getSavedJob(
  token: string,
  id: number
): Promise<SavedJobOut> {
  return request<SavedJobOut>(`/saved-jobs/${id}`, {}, token);
}

/* ─── Applications ─── */

export async function createApplication(
  token: string,
  data: ApplicationCreateIn
): Promise<ApplicationOut> {
  return request<ApplicationOut>(
    "/applications",
    { method: "POST", body: JSON.stringify(data) },
    token
  );
}

export async function listApplications(
  token: string
): Promise<ApplicationOut[]> {
  return request<ApplicationOut[]>("/applications", {}, token);
}

export async function getApplication(
  token: string,
  id: number
): Promise<ApplicationOut> {
  return request<ApplicationOut>(`/applications/${id}`, {}, token);
}

export async function getPrefilledForm(
  token: string,
  id: number
): Promise<PrefilledFormOut> {
  return request<PrefilledFormOut>(
    `/applications/${id}/prefilled-form`,
    {},
    token
  );
}

export async function confirmApplication(
  token: string,
  id: number,
  data: ConfirmApplicationIn
): Promise<ApplicationOut> {
  return request<ApplicationOut>(
    `/applications/${id}/confirm`,
    { method: "POST", body: JSON.stringify(data) },
    token
  );
}

export async function markApplicationSentManually(
  token: string,
  id: number
): Promise<ApplicationOut> {
  return request<ApplicationOut>(
    `/applications/${id}/mark-sent`,
    { method: "POST" },
    token
  );
}
