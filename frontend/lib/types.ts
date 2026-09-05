/* ─── Auth ─── */

export interface User {
  id: number;
  email: string;
  is_admin: boolean;
}

export interface Token {
  access_token: string;
  token_type: string;
}

/* ─── Candidate Profile ─── */

export interface CandidateProfileIn {
  first_name: string;
  last_name: string;
  phone: string;
  address?: string | null;
  linkedin_url?: string | null;
  portfolio_url?: string | null;
  work_authorization: string;
  salary_expectation?: string | null;
}

export interface CandidateProfileOut {
  first_name: string;
  last_name: string;
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
  salary_currency: string | null;
  weekly_application_goal: number | null;
  has_profile_photo: boolean;
}

export interface OnboardingProfileIn {
  first_name: string;
  last_name: string;
  desired_job_titles: string[];
  seniority_level: string | null;
  desired_locations: string[];
  remote_preference: boolean;
  contract_types: string[];
  salary_min: number | null;
  salary_max: number | null;
  salary_currency?: string | null;
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
  documents: PersonalizedDocumentOut[];
}

/* ─── Personalized Document ─── */

export interface CvExperienceEntry {
  title: string;
  company: string;
  dates: string;
  bullets: string[];
}

export interface HonestyAssessment {
  fit_summary: string;
  concerns: string[];
  strengths: string[];
}

export interface KeywordOmission {
  keyword: string;
  reason: string;
}

export interface ChangelogEntry {
  section: string;
  change: string;
  reason: string;
}

export interface RewrittenCv {
  summary: string;
  experience: CvExperienceEntry[];
  education: string[];
  skills: string[];
  honesty_assessment: HonestyAssessment;
  keywords_added: string[];
  keywords_already_present: string[];
  keywords_deliberately_omitted: KeywordOmission[];
  changelog: ChangelogEntry[];
}

export type CvTemplate = "classic" | "modern" | "minimal";

export interface CvStyleOptions {
  font?: "dejavu";
  accent_color?: string;
  margins?: number;
  spacing?: "compact" | "normal" | "relaxed";
}

export interface PersonalizedDocumentOut {
  kind: "cv" | "lettre";
  needs_review: boolean;
  created_at: string;
  updated_at: string;
  ats_score_before?: number | null;
  ats_score_after?: number | null;
  content_json?: RewrittenCv | null;
}

/* ─── Generation Jobs ─── */

export interface GenerationJobStarted {
  job_id: string;
}

export interface CvGenerationResult {
  kind: "cv";
  needs_review: boolean;
  ats_score_before: number;
  ats_score_after: number;
  content: RewrittenCv;
  template: CvTemplate;
  created_at: string;
  updated_at: string;
}

export type LetterTone = "sobre" | "chaleureux" | "direct" | "formel";

export interface LetterGenerationResult {
  kind: "lettre";
  needs_review: boolean;
  created_at: string;
  updated_at: string;
}

export interface GenerationJobOut<
  TResult = CvGenerationResult | LetterGenerationResult,
> {
  status: "running" | "done" | "error";
  current_step: string;
  step_index: number;
  total_steps: number;
  result: TResult | null;
  error: string | null;
}

/* ─── Interview Prep ─── */

export interface CompanyFacts {
  founding_year: number | null;
  headquarters: string | null;
  sector: string | null;
  revenue: string | null;
  ceo: string | null;
  confidence: "verified_web_search" | "general_knowledge_unverified";
}

export interface RecentNewsItem {
  headline: string;
  summary: string;
  source_url: string | null;
}

export interface ProbableQuestion {
  question: string;
  targets_weak_point: string | null;
  model_answer: string;
}

export interface PracticalExercise {
  title: string;
  prompt: string;
  pitfalls_to_avoid: string[];
  difficulty: "facile" | "moyen" | "difficile";
}

export interface CoachingChecklistContent {
  before: string[];
  during: string[];
  after: string[];
}

export interface InterviewPrepDossierContent {
  narrative_angle: string;
  company_facts: CompanyFacts;
  recent_news: RecentNewsItem[];
  probable_questions: ProbableQuestion[];
  practical_exercises: PracticalExercise[];
  coaching_checklist: CoachingChecklistContent;
}

export interface InterviewPrepSource {
  title?: string;
  url?: string;
}

export interface InterviewPrepDossierOut {
  saved_job_id: number;
  persona: string;
  extra_context: string | null;
  web_search_used: boolean;
  dossier: InterviewPrepDossierContent;
  sources: InterviewPrepSource[] | null;
  created_at: string;
  updated_at: string;
}

export interface InterviewPrepRequestIn {
  persona: string;
  extra_context: string | null;
  use_web_search: boolean;
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
  is_remote: boolean;
  compatibility_score: number;
}

export interface CompatibilityScoreBreakdown {
  // null = pas assez de données pour juger ce critère (jamais une valeur
  // neutre devinée).
  title: number | null;
  location: number | null;
  seniority: number | null;
  salary: number | null;
  freshness: number | null;
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
  funnel_stage: FunnelStage;
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

/* ─── Dashboard: Kanban + calendar ─── */

export type FunnelStage =
  | "postule"
  | "entretien_programme"
  | "proposition"
  | "refusee";

export interface KanbanSavedJobCard {
  id: number;
  title: string;
  company: string;
  offer_url: string;
  created_at: string;
}

export interface KanbanBoardOut {
  sauvegardees: KanbanSavedJobCard[];
  postule: ApplicationOut[];
  entretien_programme: ApplicationOut[];
  proposition: ApplicationOut[];
  refusee: ApplicationOut[];
}

export type InterviewType = "rh" | "manager" | "direction" | "jury" | "autre";

export interface InterviewIn {
  scheduled_at: string;
  interview_type: InterviewType;
  location_or_link?: string | null;
  notes?: string | null;
}

export interface InterviewOut {
  id: number;
  application_id: number;
  scheduled_at: string;
  interview_type: InterviewType;
  location_or_link: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface InterviewCalendarEntryOut {
  id: number;
  application_id: number;
  scheduled_at: string;
  interview_type: InterviewType;
  location_or_link: string | null;
  notes: string | null;
  company_name: string;
  job_title: string;
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
  code?: string;

  constructor(status: number, detail: string, code?: string) {
    super(detail);
    this.status = status;
    this.detail = detail;
    this.code = code;
  }
}

export interface UsageItem {
  feature: string;
  label: string;
  used: number;
  limit: number;
  reset_date: string;
}

/* ─── Admin ─── */

export interface AdminOverview {
  users_total: number;
  users_active_7d: number;
  llm_calls_this_month: Record<string, number>;
  tokens_this_month: { input: number; output: number };
  llm_features_enabled: boolean;
}

export interface AdminUser {
  id: number;
  email: string;
  created_at: string;
  is_admin: boolean;
  is_active: boolean;
  invite_note: string | null;
  consent_version: string | null;
  consent_accepted_at: string | null;
  last_activity_at: string | null;
  quota_overrides: Record<string, number> | null;
  usage: UsageItem[];
}

export interface AdminInvite {
  code: string;
  note: string | null;
  created_at: string;
  expires_at: string | null;
  used_by_email: string | null;
  used_at: string | null;
}

export interface AdminFeedback {
  id: number;
  user_email: string | null;
  page: string;
  message: string;
  created_at: string;
  handled_at: string | null;
}

export type AccessRequestStatus = "pending" | "approved" | "dismissed";

export interface AdminAccessRequest {
  id: number;
  email: string;
  note: string;
  status: AccessRequestStatus;
  created_at: string;
  handled_at: string | null;
  invite_code: string | null;
}
