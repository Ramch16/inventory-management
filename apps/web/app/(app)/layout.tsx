"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { AppShell } from "@/components/layout/app-shell";
import { Skeleton } from "@/components/ui/skeleton";
import { useSession } from "@/hooks/use-session";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { data: user, isLoading, isError } = useSession();

  useEffect(() => {
    if (isError) {
      router.replace("/login");
    }
  }, [isError, router]);

  if (isLoading || !user) {
    return (
      <div className="mx-auto max-w-5xl space-y-4 p-8">
        <Skeleton className="h-8 w-56" />
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  return <AppShell>{children}</AppShell>;
}
