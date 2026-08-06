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
