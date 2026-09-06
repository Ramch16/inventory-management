"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";

import { ApiError } from "@/lib/api/client";
import { endpoints, queryKeys } from "@/lib/api/queries";
import type { User } from "@/lib/api/types";

export function useSession() {
  return useQuery<User, ApiError>({
    queryKey: queryKeys.session,
    queryFn: endpoints.me,
    retry: false,
    staleTime: 60_000,
  });
}

export function useLogout() {
  const router = useRouter();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: endpoints.logout,
    onSuccess: () => {
      queryClient.clear();
      router.replace("/login");
    },
  });
}
