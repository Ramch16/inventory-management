/** Query keys and typed endpoint wrappers used by the React Query hooks. */

import { api } from "@/lib/api/client";
import type {
  ApplicationDetail,
  ApplicationSummary,
  AutomationSettings,
  Certification,
  DiscoveryResult,
  JobCard,
  JobDetail,
  JobPreference,
  JobSource,
  MatchSummary,
  Page,
  Intervention,
  OnboardingStatus,
  ResumeTemplate,
  ResumeVersion,
  DashboardResponse,
  Education,
  Experience,
  Notification,
  Profile,
  ProfileCompleteness,
  Resume,
  ResumeImportResult,
  ResumeSummary,
  SessionResponse,
  Skill,
  User,
  WorkAuthorization,
} from "@/lib/api/types";

export const queryKeys = {
  session: ["session"] as const,
  profile: ["profile"] as const,
  completeness: ["profile", "completeness"] as const,
  experience: ["profile", "experience"] as const,
  education: ["profile", "education"] as const,
  skills: ["profile", "skills"] as const,
  certifications: ["profile", "certifications"] as const,
  resumes: ["resumes"] as const,
  resume: (id: string) => ["resumes", id] as const,
  dashboard: ["dashboard"] as const,
  jobs: (filters: Record<string, unknown> = {}) => ["jobs", filters] as const,
  job: (id: string) => ["jobs", "detail", id] as const,
  preferences: ["preferences"] as const,
  resumeVersions: (jobId: string) => ["resume-versions", jobId] as const,
  applications: (filters: Record<string, unknown> = {}) => ["applications", filters] as const,
  application: (id: string) => ["applications", "detail", id] as const,
  interventions: (status: string) => ["interventions", status] as const,
  intervention: (id: string) => ["interventions", "detail", id] as const,
  automationSettings: ["automation-settings"] as const,
  onboarding: ["onboarding"] as const,
  jobSources: ["job-sources"] as const,
  notifications: ["notifications"] as const,
  unreadCount: ["notifications", "unread-count"] as const,
};

export const endpoints = {
  // auth
  me: () => api.get<User>("/auth/me"),
  login: (email: string, password: string) =>
    api.post<SessionResponse>("/auth/login", { email, password }),
  register: (payload: {
    email: string;
    password: string;
    first_name?: string;
    last_name?: string;
  }) => api.post<SessionResponse>("/auth/register", payload),
  logout: () => api.post<void>("/auth/logout"),
  requestVerification: () => api.post<{ message: string }>("/auth/verify-email/request"),
  confirmVerification: (token: string) =>
    api.post<User>("/auth/verify-email/confirm", { token }),
  forgotPassword: (email: string) =>
    api.post<{ message: string }>("/auth/password/forgot", { email }),
  resetPassword: (token: string, password: string) =>
    api.post<void>("/auth/password/reset", { token, password }),
  changePassword: (current_password: string, new_password: string) =>
    api.post<void>("/auth/password/change", { current_password, new_password }),
  deleteAccount: (password: string | null) =>
    api.delete<void>("/auth/account", { password, confirmation: "DELETE" }),

  // profile
  profile: () => api.get<Profile>("/profile"),
  updateProfile: (payload: Partial<Profile>) => api.put<Profile>("/profile", payload),
  workAuthorization: () => api.get<WorkAuthorization>("/profile/work-authorization"),
  updateWorkAuthorization: (payload: {
    authorization_country: string;
    authorization_type: string;
    authorization_expires_on?: string | null;
    requires_sponsorship_now: boolean;
    requires_sponsorship_future: boolean;
    confirmed: boolean;
  }) => api.put<WorkAuthorization>("/profile/work-authorization", payload),
  completeness: () => api.get<ProfileCompleteness>("/profile/completeness"),

  experience: () => api.get<Experience[]>("/profile/experience"),
  addExperience: (payload: Partial<Experience>) =>
    api.post<Experience>("/profile/experience", payload),
  updateExperience: (id: string, payload: Partial<Experience>) =>
    api.put<Experience>(`/profile/experience/${id}`, payload),
  deleteExperience: (id: string) => api.delete<void>(`/profile/experience/${id}`),

  education: () => api.get<Education[]>("/profile/education"),
  addEducation: (payload: Partial<Education>) =>
    api.post<Education>("/profile/education", payload),
  deleteEducation: (id: string) => api.delete<void>(`/profile/education/${id}`),

  skills: () => api.get<Skill[]>("/profile/skills"),
  addSkill: (payload: Partial<Skill>) => api.post<Skill>("/profile/skills", payload),
  updateSkill: (id: string, payload: Partial<Skill>) =>
    api.put<Skill>(`/profile/skills/${id}`, payload),
  deleteSkill: (id: string) => api.delete<void>(`/profile/skills/${id}`),

  certifications: () => api.get<Certification[]>("/profile/certifications"),
  addCertification: (payload: Partial<Certification>) =>
    api.post<Certification>("/profile/certifications", payload),
  deleteCertification: (id: string) => api.delete<void>(`/profile/certifications/${id}`),

  // resumes
  resumes: () => api.get<ResumeSummary[]>("/resumes"),
  resume: (id: string) => api.get<Resume>(`/resumes/${id}`),
  uploadResume: (file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return api.upload<Resume>("/resumes/upload", formData);
  },
  createResumeFromText: (title: string, content: string) =>
    api.post<Resume>("/resumes/text", { title, content, set_as_master: true }),
  setMasterResume: (id: string) => api.post<Resume>(`/resumes/${id}/master`),
  importResume: (id: string) => api.post<ResumeImportResult>(`/resumes/${id}/import`, {}),
  deleteResume: (id: string) => api.delete<void>(`/resumes/${id}`),

  // jobs
  searchJobs: (payload: {
    keywords?: string[];
    titles?: string[];
    locations?: string[];
    remote_only?: boolean;
    sources?: string[];
  }) => api.post<DiscoveryResult>("/jobs/search", payload),
  jobs: (params: {
    page?: number;
    page_size?: number;
    min_score?: number;
    recommendation?: string;
    company?: string;
  }) => {
    const query = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== "") {
        query.set(key, String(value));
      }
    });
    const suffix = query.toString();
    return api.get<Page<JobCard>>(`/jobs${suffix ? `?${suffix}` : ""}`);
  },
  job: (id: string) => api.get<JobDetail>(`/jobs/${id}`),
  matchJob: (id: string) => api.post<MatchSummary>(`/jobs/${id}/match`),
  rescoreJobs: () => api.post<{ rescored: number }>("/jobs/rescore"),
  decideJob: (id: string, decision: "approve" | "skip") =>
    api.post<MatchSummary>(`/jobs/${id}/decision`, { decision }),
  preferences: () => api.get<JobPreference>("/preferences"),
  updatePreferences: (payload: Partial<JobPreference>) =>
    api.put<JobPreference>("/preferences", payload),
  jobSources: () => api.get<JobSource[]>("/job-sources"),

  // tailored resumes
  tailorResume: (payload: {
    job_id: string;
    template?: ResumeTemplate;
    max_pages?: number;
    include_cover_letter?: boolean;
  }) => api.post<ResumeVersion>("/resumes/tailor", payload),
  resumeVersionsForJob: (jobId: string) =>
    api.get<ResumeVersion[]>(`/resume-versions/for-job/${jobId}`),
  resumeVersion: (id: string) => api.get<ResumeVersion>(`/resume-versions/${id}`),

  // applications
  createApplication: (payload: { job_id: string; auto_submit?: boolean; generate_resume?: boolean }) =>
    api.post<ApplicationSummary>("/applications", payload),
  applications: (params: { page?: number; page_size?: number; status?: string }) => {
    const query = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== "") query.set(key, String(value));
    });
    const suffix = query.toString();
    return api.get<Page<ApplicationSummary>>(`/applications${suffix ? `?${suffix}` : ""}`);
  },
  application: (id: string) => api.get<ApplicationDetail>(`/applications/${id}`),
  startApplication: (id: string) =>
    api.post<{ task_id: string; status: string }>(`/applications/${id}/start`),
  cancelApplication: (id: string) => api.post<void>(`/applications/${id}/cancel`),
  updateApplicationStatus: (id: string, status: string, note?: string) =>
    api.put<ApplicationSummary>(`/applications/${id}/status`, { status, note }),

  // interventions
  interventions: (status = "open") =>
    api.get<Page<Intervention>>(`/interventions?status=${status}`),
  intervention: (id: string) => api.get<Intervention>(`/interventions/${id}`),
  continueIntervention: (id: string, payload: { answers?: Record<string, string>; otp_code?: string }) =>
    api.post<{ task_id: string; status: string }>(`/interventions/${id}/continue`, payload),
  cancelIntervention: (id: string) => api.post<void>(`/interventions/${id}/cancel`),

  // onboarding
  onboarding: () => api.get<OnboardingStatus>("/profile/onboarding"),
  completeOnboarding: () =>
    api.post<OnboardingStatus>("/profile/onboarding/complete", { confirmed: true }),

  // automation settings
  automationSettings: () => api.get<AutomationSettings>("/automation-settings"),
  updateAutomationSettings: (payload: Partial<AutomationSettings>) =>
    api.put<AutomationSettings>("/automation-settings", payload),
  setPause: (paused: boolean) => api.post<AutomationSettings>("/automation/pause", { paused }),

  // dashboard
  dashboard: () => api.get<DashboardResponse>("/dashboard"),
  notifications: () => api.get<Notification[]>("/notifications"),
  unreadCount: () => api.get<{ count: number }>("/notifications/unread-count"),
  markNotificationRead: (id: string) => api.post<void>(`/notifications/${id}/read`),
  markAllNotificationsRead: () => api.post<{ updated: number }>("/notifications/read-all"),
};
