/** Query keys and typed endpoint wrappers used by the React Query hooks. */

import { api } from "@/lib/api/client";
import type {
  Certification,
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

  // dashboard
  dashboard: () => api.get<DashboardResponse>("/dashboard"),
  notifications: () => api.get<Notification[]>("/notifications"),
  unreadCount: () => api.get<{ count: number }>("/notifications/unread-count"),
  markNotificationRead: (id: string) => api.post<void>(`/notifications/${id}/read`),
  markAllNotificationsRead: () => api.post<{ updated: number }>("/notifications/read-all"),
};
