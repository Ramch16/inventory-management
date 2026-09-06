"use client";

import { useQuery } from "@tanstack/react-query";

import { endpoints, queryKeys } from "@/lib/api/queries";

export function useProfile() {
  return useQuery({ queryKey: queryKeys.profile, queryFn: endpoints.profile });
}

export function useCompleteness() {
  return useQuery({ queryKey: queryKeys.completeness, queryFn: endpoints.completeness });
}

export function useExperience() {
  return useQuery({ queryKey: queryKeys.experience, queryFn: endpoints.experience });
}

export function useEducation() {
  return useQuery({ queryKey: queryKeys.education, queryFn: endpoints.education });
}

export function useSkills() {
  return useQuery({ queryKey: queryKeys.skills, queryFn: endpoints.skills });
}

export function useCertifications() {
  return useQuery({ queryKey: queryKeys.certifications, queryFn: endpoints.certifications });
}
