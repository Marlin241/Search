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
  followed_companies: string[];
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
}
