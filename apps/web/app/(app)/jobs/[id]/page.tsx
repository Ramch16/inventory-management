"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ExternalLink } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";

import { MatchScore } from "@/components/jobs/match-score";
import { TailoredResumePanel } from "@/components/resume/tailored-resume-panel";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { ApiError } from "@/lib/api/client";
import { endpoints, queryKeys } from "@/lib/api/queries";
import { formatDate, titleCase } from "@/lib/utils";

export default function JobDetailPage() {
  const params = useParams<{ id: string }>();
  const jobId = params.id;
  const router = useRouter();
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const job = useQuery({
    queryKey: queryKeys.job(jobId),
    queryFn: () => endpoints.job(jobId),
  });

  const rescore = useMutation({
    mutationFn: () => endpoints.matchJob(jobId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.job(jobId) });
      toast({ title: "Match recalculated", variant: "success" });
    },
  });

  const apply = useMutation({
    mutationFn: () => endpoints.createApplication({ job_id: jobId }),
    onSuccess: (application) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.job(jobId) });
      queryClient.invalidateQueries({ queryKey: ["applications"] });
      toast({
        title: "Application created",
        description: "Review it, then start the automation when you are ready.",
        variant: "success",
      });
      router.push(`/applications/${application.id}`);
    },
    onError: (error) =>
      toast({
        title: "Cannot apply to this job",
        description: error instanceof ApiError ? error.message : "Something went wrong.",
        variant: "error",
      }),
  });

  const decide = useMutation({
    mutationFn: (decision: "approve" | "skip") => endpoints.decideJob(jobId, decision),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.job(jobId) }),
    onError: (error) =>
      toast({
        title: "Cannot approve this job",
        description: error instanceof ApiError ? error.message : "Something went wrong.",
        variant: "error",
      }),
  });

  if (job.isLoading || !job.data) {
    return <Skeleton className="h-96 w-full max-w-4xl" />;
  }

  const detail = job.data;
  const match = detail.match;
  const components = match
    ? [
        ["Skills", match.skills_score],
        ["Experience", match.experience_score],
        ["Title", match.title_score],
        ["Seniority", match.seniority_score],
        ["Education", match.education_score],
        ["Location", match.location_score],
        ["Authorization", match.authorization_score],
      ]
    : [];

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <Link
        href="/jobs"
        className="inline-flex items-center gap-1 text-sm text-muted-foreground underline-offset-4 hover:underline"
      >
        <ArrowLeft className="h-3.5 w-3.5" aria-hidden />
        Back to jobs
      </Link>

      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{detail.title}</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {detail.company_name}
            {detail.location ? ` · ${detail.location}` : ""} · {titleCase(detail.remote_type)}
            {detail.detected_ats ? ` · ${titleCase(detail.detected_ats)}` : ""}
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            Discovered {formatDate(detail.discovered_at)}
            {detail.source_slug ? ` from ${detail.source_slug}` : ""}
          </p>
        </div>
        <div className="flex items-center gap-3">
          {match ? (
            <MatchScore score={match.overall_score} recommendation={match.recommendation} />
          ) : null}
          <div className="flex flex-col gap-1.5">
            <Button
              size="sm"
              disabled={decide.isPending || match?.hard_requirement_failed}
              onClick={() => decide.mutate("approve")}
            >
              Approve
            </Button>
            <Button size="sm" variant="ghost" onClick={() => decide.mutate("skip")}>
              Skip
            </Button>
            <Button size="sm" variant="ghost" onClick={() => rescore.mutate()}>
              Rescore
            </Button>
            {detail.application_status ? (
              <Button asChild size="sm" variant="secondary">
                <Link href="/applications">View application</Link>
              </Button>
            ) : (
              <Button
                size="sm"
                variant="secondary"
                disabled={apply.isPending || match?.hard_requirement_failed}
                onClick={() => apply.mutate()}
              >
                {apply.isPending ? "Preparing…" : "Apply"}
              </Button>
            )}
          </div>
        </div>
      </div>

      {match?.hard_requirement_failed ? (
        <Alert variant="warning">
          <p className="font-medium">This job cannot be approved for automation.</p>
          <ul className="mt-1 space-y-1 text-sm text-muted-foreground">
            {match.risks.map((risk) => (
              <li key={risk}>· {risk}</li>
            ))}
          </ul>
        </Alert>
      ) : null}

      {match ? (
        <Card>
          <CardHeader>
            <CardTitle>Match analysis</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">{match.explanation}</p>
            <div className="grid gap-3 sm:grid-cols-2">
              {components.map(([label, value]) => (
                <div key={label as string}>
                  <div className="mb-1 flex items-center justify-between text-xs">
                    <span>{label}</span>
                    <span className="tabular text-muted-foreground">{value}</span>
                  </div>
                  <Progress value={value as number} />
                </div>
              ))}
            </div>
            <div className="flex flex-wrap gap-1.5">
              {match.matched_skills.map((skill) => (
                <Badge key={skill} variant="success">
                  {skill}
                </Badge>
              ))}
              {match.missing_skills.map((skill) => (
                <Badge key={skill} variant="outline">
                  {skill}
                </Badge>
              ))}
            </div>
          </CardContent>
        </Card>
      ) : null}

      <TailoredResumePanel jobId={jobId} />

      <Card>
        <CardHeader>
          <CardTitle>Posting</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
            {[
              ["Employment type", titleCase(detail.employment_type)],
              [
                "Salary",
                detail.salary_min && detail.salary_max
                  ? `${detail.salary_min.toLocaleString()} – ${detail.salary_max.toLocaleString()} ${detail.salary_currency ?? ""}`
                  : "Not stated",
              ],
              ["Experience required", detail.experience_required_years ? `${detail.experience_required_years} years` : "Not stated"],
              ["Education", detail.education ?? "Not stated"],
            ].map(([label, value]) => (
              <div key={label} className="flex gap-2">
                <dt className="w-40 shrink-0 text-muted-foreground">{label}</dt>
                <dd>{value}</dd>
              </div>
            ))}
          </dl>

          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Sponsorship
            </p>
            <p className="mt-1 text-sm">
              {detail.sponsorship_information
                ? `“${detail.sponsorship_information.trim()}”`
                : "The posting does not mention sponsorship."}
            </p>
          </div>

          {detail.requirements.length > 0 ? (
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Requirements
              </p>
              <ul className="mt-1 space-y-1 text-sm">
                {detail.requirements.map((item) => (
                  <li key={item}>· {item}</li>
                ))}
              </ul>
            </div>
          ) : null}

          {detail.preferred_qualifications.length > 0 ? (
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Preferred
              </p>
              <ul className="mt-1 space-y-1 text-sm">
                {detail.preferred_qualifications.map((item) => (
                  <li key={item}>· {item}</li>
                ))}
              </ul>
            </div>
          ) : null}

          {detail.description ? (
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Full description
              </p>
              {/* Employer text is rendered as plain text, never as HTML. */}
              <p className="mt-1 whitespace-pre-wrap text-sm text-muted-foreground">
                {detail.description}
              </p>
            </div>
          ) : null}

          {detail.apply_url ? (
            <Button asChild variant="outline" size="sm">
              <a href={detail.apply_url} target="_blank" rel="noreferrer">
                <ExternalLink className="h-3.5 w-3.5" aria-hidden />
                Open the original posting
              </a>
            </Button>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
