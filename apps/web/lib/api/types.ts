/**
 * Response contracts mirrored from the FastAPI Pydantic models.
 * Keep these in sync with apps/api/jobapply_api/schemas.
 */

export type RemoteType = "remote" | "hybrid" | "onsite" | "unknown";

export type EmploymentType =
  | "full_time"
  | "part_time"
  | "contract"
  | "internship"
  | "temporary"
  | "unknown";

export type AuthorizationType =
  | "citizen"
  | "permanent_resident"
  | "work_visa"
  | "student_visa"
  | "work_permit"
  | "other";

export type SkillCategory =
  | "language"
  | "framework"
  | "database"
  | "cloud"
  | "analytics"
  | "devops"
  | "soft"
  | "other";

export interface User {
  id: string;
  email: string;
  role: "user" | "admin";
  is_active: boolean;
  email_verified_at: string | null;
  automation_paused: boolean;
  onboarding_completed_at: string | null;
  created_at: string;
}

export interface SessionResponse {
  user: User;
  csrf_token: string;
}

export interface WorkAuthorization {
  authorization_country: string | null;
  authorization_type: AuthorizationType | null;
  authorization_expires_on: string | null;
  requires_sponsorship_now: boolean | null;
  requires_sponsorship_future: boolean | null;
  work_authorization_confirmed_at: string | null;
  declared: boolean;
}

export interface Profile {
  id: string;
  user_id: string;
  first_name: string | null;
  last_name: string | null;
  preferred_name: string | null;
  email: string | null;
  phone: string | null;
  city: string | null;
  state: string | null;
  country: string | null;
  postal_code: string | null;
  linkedin_url: string | null;
  github_url: string | null;
  portfolio_url: string | null;
  current_title: string | null;
  years_experience: number | null;
  summary: string | null;
  desired_titles: string[] | null;
  desired_industries: string[] | null;
  desired_employment_types: string[] | null;
  desired_locations: string[] | null;
  remote_preference: RemoteType | null;
  salary_min: number | null;
  salary_max: number | null;
  salary_currency: string | null;
  open_to_relocation: boolean | null;
  work_authorization: WorkAuthorization | null;
  updated_at: string;
}

export interface Experience {
  id: string;
  company: string;
  title: string;
  location: string | null;
  employment_type: EmploymentType | null;
  start_date: string | null;
  end_date: string | null;
  is_current: boolean;
  description: string | null;
  accomplishments: string[];
  technologies: string[];
  skills: string[];
  sort_order: number;
}

export interface Education {
  id: string;
  institution: string;
  degree: string | null;
  field_of_study: string | null;
  location: string | null;
  start_date: string | null;
  end_date: string | null;
  is_current: boolean;
  gpa: number | null;
  relevant_coursework: string[];
  sort_order: number;
}

export interface Skill {
  id: string;
  name: string;
  category: SkillCategory;
  years_experience: number | null;
  proficiency: string | null;
  is_verified: boolean;
  last_used_year: number | null;
}

export interface Certification {
  id: string;
  name: string;
  issuer: string | null;
  issued_on: string | null;
  expires_on: string | null;
  credential_id: string | null;
  credential_url: string | null;
  is_verified: boolean;
}

export interface ProfileCompleteness {
  score: number;
  missing: string[];
  blocks_automation: string[];
  ready_for_automation: boolean;
}

export interface ParsedResume {
  contact: {
    full_name: string | null;
    email: string | null;
    phone: string | null;
    location: string | null;
    linkedin_url: string | null;
    github_url: string | null;
    portfolio_url: string | null;
  };
  summary: string | null;
  skills: string[];
  positions: Array<{
    company: string | null;
    title: string | null;
    location: string | null;
    start_date: string | null;
    end_date: string | null;
    is_current: boolean;
    bullets: string[];
  }>;
  education: Array<{
    institution: string | null;
    degree: string | null;
    field_of_study: string | null;
    end_date: string | null;
    gpa: number | null;
  }>;
  certifications: Array<Record<string, unknown>>;
  projects: Array<Record<string, unknown>>;
  warnings: string[];
}

export interface Resume {
  id: string;
  title: string;
  source_kind: string;
  is_master: boolean;
  original_filename: string | null;
  original_content_type: string | null;
  original_size_bytes: number | null;
  parse_status: string;
  parse_error: string | null;
  parsed_at: string | null;
  created_at: string;
  updated_at: string;
  structured: ParsedResume | null;
}

export interface ResumeSummary {
  id: string;
  title: string;
  source_kind: string;
  is_master: boolean;
  original_filename: string | null;
  parse_status: string;
  created_at: string;
}

export interface ResumeImportResult {
  experience_added: number;
  education_added: number;
  skills_added: number;
  certifications_added: number;
  profile_updated: boolean;
  notes: string[];
}

export interface DashboardCounters {
  jobs_discovered: number;
  jobs_matched: number;
  applications_total: number;
  applications_submitted: number;
  applications_this_week: number;
  applications_this_month: number;
  applications_failed: number;
  applications_in_progress: number;
  interviews: number;
  offers: number;
  rejections: number;
  open_interventions: number;
  average_match_score: number;
  automation_success_rate: number;
  failure_rate: number;
}

export interface ProfileReadiness {
  profile_score: number;
  has_master_resume: boolean;
  work_authorization_declared: boolean;
  automation_enabled: boolean;
  automation_paused: boolean;
  blockers: string[];
}

export interface RecentApplication {
  id: string;
  status: string;
  company: string;
  title: string;
  match_score: number | null;
  submitted_at: string | null;
  created_at: string;
}

export interface AttentionItem {
  id: string;
  application_id: string;
  type: string;
  reason: string;
  current_step: string | null;
  company: string;
  title: string;
  created_at: string;
}

export interface DashboardResponse {
  counters: DashboardCounters;
  readiness: ProfileReadiness;
  recent_applications: RecentApplication[];
  attention_required: AttentionItem[];
}

export interface Notification {
  id: string;
  kind: string;
  channel: string;
  title: string;
  body: string | null;
  link: string | null;
  read_at: string | null;
  created_at: string;
}

// --------------------------------------------------------------------------- jobs
export type MatchRecommendation = "APPLY" | "REVIEW" | "SKIP";

export interface MatchSummary {
  overall_score: number;
  skills_score: number;
  experience_score: number;
  education_score: number;
  location_score: number;
  authorization_score: number;
  title_score: number;
  seniority_score: number;
  recommendation: MatchRecommendation;
  matched_skills: string[];
  missing_skills: string[];
  risks: string[];
  hard_requirement_failed: boolean;
  explanation: string | null;
  user_decision: string | null;
}

export interface JobCard {
  id: string;
  company_name: string;
  title: string;
  location: string | null;
  remote_type: RemoteType;
  employment_type: EmploymentType;
  salary_min: number | null;
  salary_max: number | null;
  salary_currency: string | null;
  detected_ats: string | null;
  apply_url: string | null;
  status: string;
  discovered_at: string;
  expiration_date: string | null;
  sponsorship_offered: boolean | null;
  match: MatchSummary | null;
  application_status: string | null;
}

export interface JobDetail extends JobCard {
  description: string | null;
  requirements: string[];
  preferred_qualifications: string[];
  skills: string[];
  education: string | null;
  experience_required_years: number | null;
  seniority: string | null;
  sponsorship_information: string | null;
  posting_url: string | null;
  source_slug: string | null;
}

export interface Page<T> {
  items: T[];
  page: number;
  page_size: number;
  total: number;
}

export interface DiscoveryResult {
  fetched: number;
  created: number;
  duplicates: number;
  scored: number;
  errors: string[];
}

export interface MatchWeights {
  skills: number;
  experience: number;
  title: number;
  education: number;
  location: number;
  authorization: number;
}

export interface JobPreference {
  id: string;
  name: string;
  is_active: boolean;
  target_titles: string[] | null;
  excluded_titles: string[] | null;
  target_companies: string[] | null;
  excluded_companies: string[] | null;
  locations: string[] | null;
  remote_preference: RemoteType | null;
  salary_min: number | null;
  experience_min_years: number | null;
  experience_max_years: number | null;
  employment_types: string[] | null;
  industries: string[] | null;
  keywords: string[] | null;
  excluded_keywords: string[] | null;
  requires_sponsorship: boolean | null;
  match_weights: MatchWeights | null;
  updated_at: string;
}

export interface JobSource {
  id: string;
  slug: string;
  name: string;
  kind: string;
  enabled: boolean;
  last_run_at: string | null;
  last_error: string | null;
}

// ---------------------------------------------------------------- tailored resumes
export type ResumeTemplate =
  | "ats_classic"
  | "modern_professional"
  | "technical"
  | "minimal";

export interface ResumeScore {
  ats_readability: number;
  keyword_coverage: number;
  skill_coverage: number;
  experience_relevance: number;
  formatting_quality: number;
  factual_consistency: number;
  overall: number;
  notes: string[];
}

export interface ProvenanceRecord {
  generated_text: string;
  source_ids: string[];
  confidence: number;
  section: string | null;
}

export interface TruthReport {
  allowed: boolean;
  reasons: string[];
  rejected_statements: string[];
  rejected_by_generator: Array<{ section?: string; text?: string; reasons?: string[] }>;
  used_ai: boolean;
}

export interface ResumeVersion {
  id: string;
  resume_id: string;
  job_id: string | null;
  version: number;
  label: string | null;
  template: ResumeTemplate;
  quality: ResumeScore | null;
  truth_report: TruthReport | null;
  provenance: ProvenanceRecord[];
  content: Record<string, unknown> | null;
  cover_letter_text: string | null;
  ai_provider: string | null;
  ai_model: string | null;
  docx_storage_key: string | null;
  pdf_storage_key: string | null;
  created_at: string;
}
