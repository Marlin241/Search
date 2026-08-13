export interface User {
  id: number;
  email: string;
}

export interface DiagnosticReport {
  id: number;
  created_at: string;
  overall_score: number;
  structural_score: number;
  structural_issues: string[];
  semantic_score: number;
  missing_keywords: string[];
  recommendations: string[];
}

export interface PersonalizedDocument {
  kind: "cv" | "lettre";
  needs_review: boolean;
  created_at: string;
  updated_at: string;
}

export interface CandidateProfile {
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
}

export interface CandidateProfileInput {
  full_name: string;
  phone: string;
  address: string | null;
  linkedin_url: string | null;
  portfolio_url: string | null;
  work_authorization: string;
  salary_expectation: string | null;
}

export interface SearchCriteria {
  keywords: string;
  location?: string;
  contract_type?: string;
  remote?: boolean;
  exclude_keywords: string[];
}

export interface JobListing {
  title: string;
  company: string;
  location: string | null;
  snippet: string;
  url: string;
  source: string;
  ats_type: string | null;
}

export interface JobSearchResult {
  listings: JobListing[];
  unavailable_sources: string[];
  search_id: string;
  discovery_pending: boolean;
}

export interface JobSearchDiscoveryResult {
  done: boolean;
  new_listings: JobListing[];
}

export interface SavedSearch {
  keywords: string;
  location: string | null;
  contract_type: string | null;
  remote: boolean | null;
  exclude_keywords: string[];
  timezone: string;
  enabled: boolean;
}

export interface SavedSearchInput {
  keywords: string;
  location?: string;
  contract_type?: string;
  remote?: boolean;
  exclude_keywords: string[];
  timezone: string;
  enabled: boolean;
}

export interface Application {
  id: number;
  diagnostic_id: number;
  offer_url: string;
  source: string;
  company_name: string;
  job_title: string;
  ats_type: string | null;
  status: "en_cours" | "soumise_auto" | "a_soumettre_manuellement" | "soumise_manuelle_confirmee" | "echec_soumission";
  error_message: string | null;
  submitted_at: string | null;
  created_at: string;
  updated_at: string;
  diagnostic: DiagnosticReport;
}

export interface ApplicationCreateInput {
  offer_url: string;
  offer_text?: string;
  source: string;
  company_name: string;
  job_title: string;
  ats_type?: string | null;
}

export interface FormField {
  name: string;
  label: string;
  field_type: string;
  required: boolean;
  options: string[] | null;
  value: string | null;
  is_custom: boolean;
}

export interface PrefilledForm {
  fields: FormField[];
}
