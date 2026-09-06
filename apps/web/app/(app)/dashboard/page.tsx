"use client";

import { useQuery } from "@tanstack/react-query";
import { Briefcase, CheckCircle2, Send, Target, TriangleAlert } from "lucide-react";

import { AttentionList } from "@/components/dashboard/attention-list";
import { ReadinessCard } from "@/components/dashboard/readiness-card";
import { RecentApplications } from "@/components/dashboard/recent-applications";
import { StatCard } from "@/components/dashboard/stat-card";
import { Alert } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { endpoints, queryKeys } from "@/lib/api/queries";
import { formatNumber, formatPercent } from "@/lib/utils";

export default function DashboardPage() {
  const dashboard = useQuery({ queryKey: queryKeys.dashboard, queryFn: endpoints.dashboard });

  if (dashboard.isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-9 w-48" />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          {Array.from({ length: 5 }).map((_, index) => (
            <Skeleton key={index} className="h-24" />
          ))}
        </div>
        <Skeleton className="h-64" />
      </div>
    );
  }

  if (dashboard.isError || !dashboard.data) {
    return <Alert variant="destructive">The dashboard could not be loaded. Try again shortly.</Alert>;
  }

  const { counters, readiness, recent_applications, attention_required } = dashboard.data;

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          How many applications went out, how many succeeded, and what needs you.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <StatCard
          label="Applications"
          value={formatNumber(counters.applications_submitted)}
          hint={`${formatNumber(counters.applications_this_week)} this week`}
          icon={Send}
        />
        <StatCard
          label="Success rate"
          value={formatPercent(counters.automation_success_rate)}
          hint={`${formatNumber(counters.applications_failed)} failed`}
          icon={CheckCircle2}
          tone={counters.automation_success_rate >= 80 ? "success" : "default"}
        />
        <StatCard
          label="Needs attention"
          value={formatNumber(counters.open_interventions)}
          hint="Paused for human verification"
          icon={TriangleAlert}
          tone={counters.open_interventions > 0 ? "warning" : "default"}
        />
        <StatCard
          label="Matched jobs"
          value={formatNumber(counters.jobs_matched)}
          hint={`Average score ${counters.average_match_score}`}
          icon={Target}
        />
        <StatCard
          label="Interviews"
          value={formatNumber(counters.interviews)}
          hint={`${formatNumber(counters.offers)} offers`}
          icon={Briefcase}
          tone={counters.interviews > 0 ? "success" : "default"}
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-[1fr_20rem]">
        <div className="space-y-6">
          <AttentionList items={attention_required} />
          <RecentApplications items={recent_applications} />
        </div>
        <ReadinessCard readiness={readiness} />
      </div>
    </div>
  );
}
