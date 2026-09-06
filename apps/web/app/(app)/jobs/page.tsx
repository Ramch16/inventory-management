"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Briefcase, RefreshCw, Search } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { JobCard } from "@/components/jobs/job-card";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { ApiError } from "@/lib/api/client";
import { endpoints, queryKeys } from "@/lib/api/queries";

export default function JobsPage() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [filters, setFilters] = useState({ recommendation: "", min_score: "", company: "" });
  const [page, setPage] = useState(1);

  const params = {
    page,
    page_size: 20,
    recommendation: filters.recommendation || undefined,
    min_score: filters.min_score ? Number(filters.min_score) : undefined,
    company: filters.company || undefined,
  };

  const jobs = useQuery({
    queryKey: queryKeys.jobs(params),
    queryFn: () => endpoints.jobs(params),
  });

  const sources = useQuery({ queryKey: queryKeys.jobSources, queryFn: endpoints.jobSources });

  const search = useMutation({
    mutationFn: () => endpoints.searchJobs({}),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      toast({
        title: `${result.created} new job${result.created === 1 ? "" : "s"}`,
        description: `${result.fetched} fetched · ${result.duplicates} already known · ${result.scored} scored.`,
        variant: "success",
      });
    },
    onError: (error) => {
      toast({
        title: "Search failed",
        description: error instanceof ApiError ? error.message : "Something went wrong.",
        variant: "error",
      });
    },
  });

  const rescore = useMutation({
    mutationFn: endpoints.rescoreJobs,
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      toast({ title: `Rescored ${result.rescored} jobs`, variant: "success" });
    },
  });

  const enabledSources = (sources.data ?? []).filter((source) => source.enabled);
  const totalPages = jobs.data ? Math.max(1, Math.ceil(jobs.data.total / jobs.data.page_size)) : 1;

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Jobs</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Scored against your profile. Nothing is applied to until you approve it.
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => rescore.mutate()} disabled={rescore.isPending}>
            <RefreshCw className="h-4 w-4" aria-hidden />
            {rescore.isPending ? "Rescoring…" : "Rescore"}
          </Button>
          <Button onClick={() => search.mutate()} disabled={search.isPending}>
            <Search className="h-4 w-4" aria-hidden />
            {search.isPending ? "Searching…" : "Find jobs"}
          </Button>
        </div>
      </div>

      {enabledSources.length === 0 ? (
        <Alert variant="warning">
          No job sources are enabled, so a search would return nothing. Sources that reach
          a third party are off until you turn them on.
        </Alert>
      ) : (
        <p className="text-xs text-muted-foreground">
          Searching: {enabledSources.map((source) => source.name).join(", ")}
        </p>
      )}

      <Card>
        <CardContent className="flex flex-wrap items-end gap-3 p-4">
          <div className="min-w-[10rem] flex-1 space-y-1.5">
            <label htmlFor="company-filter" className="text-sm font-medium">
              Company
            </label>
            <Input
              id="company-filter"
              value={filters.company}
              placeholder="Any"
              onChange={(event) => {
                setPage(1);
                setFilters({ ...filters, company: event.target.value });
              }}
            />
          </div>
          <div className="w-44 space-y-1.5">
            <label htmlFor="recommendation-filter" className="text-sm font-medium">
              Recommendation
            </label>
            <Select
              id="recommendation-filter"
              value={filters.recommendation}
              onChange={(event) => {
                setPage(1);
                setFilters({ ...filters, recommendation: event.target.value });
              }}
            >
              <option value="">Any</option>
              <option value="APPLY">Apply</option>
              <option value="REVIEW">Review</option>
              <option value="SKIP">Skip</option>
            </Select>
          </div>
          <div className="w-32 space-y-1.5">
            <label htmlFor="score-filter" className="text-sm font-medium">
              Min score
            </label>
            <Input
              id="score-filter"
              type="number"
              min={0}
              max={100}
              value={filters.min_score}
              onChange={(event) => {
                setPage(1);
                setFilters({ ...filters, min_score: event.target.value });
              }}
            />
          </div>
          <Button asChild variant="ghost">
            <Link href="/settings">Edit preferences</Link>
          </Button>
        </CardContent>
      </Card>

      {jobs.isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, index) => (
            <Skeleton key={index} className="h-40 w-full" />
          ))}
        </div>
      ) : (jobs.data?.items.length ?? 0) === 0 ? (
        <EmptyState
          icon={Briefcase}
          title="No jobs yet"
          description="Run a search to pull postings from your enabled sources. Each one is scored against your profile before anything is applied to."
          action={
            <Button onClick={() => search.mutate()} disabled={search.isPending}>
              Find jobs
            </Button>
          }
        />
      ) : (
        <>
          <div className="space-y-3">
            {jobs.data?.items.map((job) => (
              <JobCard key={job.id} job={job} />
            ))}
          </div>
          {totalPages > 1 ? (
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">
                Page {jobs.data?.page} of {totalPages} · {jobs.data?.total} jobs
              </span>
              <div className="flex gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  disabled={page <= 1}
                  onClick={() => setPage((current) => current - 1)}
                >
                  Previous
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={page >= totalPages}
                  onClick={() => setPage((current) => current + 1)}
                >
                  Next
                </Button>
              </div>
            </div>
          ) : null}
        </>
      )}
    </div>
  );
}
