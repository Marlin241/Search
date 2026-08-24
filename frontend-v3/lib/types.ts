/* ─── Auth ─── */

export interface User {
  id: number;
  email: string;
}

export interface Token {
  access_token: string;
  token_type: string;
}

/* ─── Candidate Profile ─── */

export interface CandidateProfileIn {
  full_name: string;
  phone: string;
  address?: string | null;
  linkedin_url?: string | null;
  portfolio_url?: string | null;
  work_authorization: string;
  salary_expectation?: string | null;
}

export interface CandidateProfileOut {
  full_name: string;
  phone: string;
  address: string | null;
  linkedin_url: string | null;
  portfolio_url: string | null;
  work_authorization: string;
  salary_expectation: string | null;
  cv_filename: string | null;
  has_cv: boolean;
  updated_at: string;
  desired_job_titles: string[] | null;
  seniority_level: string | null;
  desired_locations: string[] | null;
  remote_preference: boolean;
  contract_types: string[] | null;
  salary_min: number | null;
  salary_max: number | null;
  weekly_application_goal: number | null;
  has_profile_photo: boolean;
}

export interface OnboardingProfileIn {
  desired_job_titles: string[];
  seniority_level: string | null;
  desired_locations: string[];
  remote_preference: boolean;
  contract_types: string[];
  salary_min: number | null;
  salary_max: number | null;
  weekly_application_goal: number | null;
}

export interface ExtractedPhotoOut {
  key: string;
  preview_url: string;
}

/* ─── Diagnostic ─── */

export interface DiagnosticReport {
  id: number | null;
  created_at: string | null;
  overall_score: number;
  structural_score: number;
  structural_issues: string[];
  semantic_score: number;
  missing_keywords: string[];
  recommendations: string[];
}

/* ─── Personalized Document ─── */

export interface PersonalizedDocumentOut {
  kind: "cv" | "lettre";
  needs_review: boolean;
  created_at: string;
  updated_at: string;
}

/* ─── Saved Job (workspace) ─── */

export interface SavedJobIn {
  offer_url: string;
  title: string;
  company: string;
  location?: string | null;
  snippet: string;
  source: string;
  ats_type?: string | null;
  salary?: string | null;
}

export interface SavedJobOut {
  id: number;
  offer_url: string;
  title: string;
  company: string;
  location: string | null;
  snippet: string;
  source: string;
  ats_type: string | null;
  salary: string | null;
  has_full_offer_text: boolean;
  created_at: string;
  updated_at: string;
  latest_diagnostic: DiagnosticReport | null;
  documents: PersonalizedDocumentOut[];
  application_status: string | null;
}

/* ─── Job Search ─── */

export interface SearchCriteria {
  keywords: string;
  location?: string | null;
  contract_type?: string | null;
  remote?: boolean | null;
  exclude_keywords?: string[];
}

export interface JobListing {
  title: string;
  company: string;
  location: string | null;
  snippet: string;
  url: string;
  source: string;
  ats_type: string | null;
  salary?: string | null;
  posted_at?: string | null;
  compatibility_score: number;
}

export interface CompatibilityScoreBreakdown {
  title: number;
  location: number;
  seniority: number;
  salary: number;
  freshness: number;
  overall: number;
}

export interface CompatibilityDetailOut {
  breakdown: CompatibilityScoreBreakdown;
  summary: string;
  strengths: string[];
  concerns: string[];
}

export interface JobSearchResponse {
  listings: JobListing[];
  unavailable_sources: string[];
  search_id: string;
  discovery_pending: boolean;
}

export interface JobSearchDiscoveryResponse {
  done: boolean;
  new_listings: JobListing[];
}

export interface SavedSearchIn {
  keywords: string;
  location?: string | null;
  contract_type?: string | null;
  remote?: boolean | null;
  exclude_keywords?: string[];
  timezone?: string;
  enabled?: boolean;
}

export interface SavedSearchOut {
  keywords: string;
  location: string | null;
  contract_type: string | null;
  remote: boolean | null;
  exclude_keywords: string[];
  timezone: string;
  enabled: boolean;
}

/* ─── Applications ─── */

export interface ApplicationCreateIn {
  offer_url: string;
  offer_text?: string | null;
  source: string;
  company_name: string;
  job_title: string;
  ats_type?: string | null;
}

export interface ApplicationOut {
  id: number;
  diagnostic_id: number;
  offer_url: string;
  source: string;
  company_name: string;
  job_title: string;
  ats_type: string | null;
  status: ApplicationStatus;
  error_message: string | null;
  submitted_at: string | null;
  created_at: string;
  updated_at: string;
  diagnostic: DiagnosticReport;
}

export type ApplicationStatus =
  | "en_cours"
  | "soumise_auto"
  | "a_soumettre_manuellement"
  | "soumise_manuelle_confirmee"
  | "echec_soumission";

export interface FormField {
  name: string;
  label: string;
  field_type: string;
  required: boolean;
  options: string[] | null;
  value: string | null;
  is_custom: boolean;
}

export interface PrefilledFormOut {
  fields: FormField[];
}

export interface ConfirmApplicationIn {
  fields?: FormField[] | null;
  override_needs_review?: boolean;
}

/* ─── API Error ─── */

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
    this.detail = detail;
  }
}
