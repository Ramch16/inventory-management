"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Building2, ExternalLink, MapPin } from "lucide-react";
import Link from "next/link";

import { MatchScore } from "@/components/jobs/match-score";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useToast } from "@/components/ui/toast";
import { ApiError } from "@/lib/api/client";
import { endpoints } from "@/lib/api/queries";
import type { JobCard as JobCardType } from "@/lib/api/types";
import { titleCase } from "@/lib/utils";

function salaryLabel(job: JobCardType): string | null {
  if (job.salary_min === null && job.salary_max === null) return null;
  const format = (value: number) => `${(value / 1000).toFixed(0)}k`;
  if (job.salary_min !== null && job.salary_max !== null) {
    return `${format(job.salary_min)}–${format(job.salary_max)}`;
  }
  return format((job.salary_min ?? job.salary_max) as number);
}

function sponsorshipLabel(job: JobCardType): { text: string; variant: "success" | "destructive" | "secondary" } {
  if (job.sponsorship_offered === true) return { text: "Sponsors visas", variant: "success" };
  if (job.sponsorship_offered === false) return { text: "No sponsorship", variant: "destructive" };
  return { text: "Sponsorship not stated", variant: "secondary" };
}

export function JobCard({ job }: { job: JobCardType }) {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const match = job.match;

  const decide = useMutation({
    mutationFn: (decision: "approve" | "skip") => endpoints.decideJob(job.id, decision),
    onSuccess: (_, decision) => {
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      toast({
        title: decision === "approve" ? "Approved for application" : "Job skipped",
        variant: "success",
      });
    },
    onError: (error) => {
      toast({
        title: "Cannot approve this job",
        description:
          error instanceof ApiError ? error.message : "Something went wrong.",
        variant: "error",
      });
    },
  });

  const salary = salaryLabel(job);
  const sponsorship = sponsorshipLabel(job);

  return (
    <Card>
      <CardContent className="p-4">
        <div className="flex items-start gap-4">
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <Link
                href={`/jobs/${job.id}`}
                className="truncate font-medium underline-offset-4 hover:underline"
              >
                {job.title}
              </Link>
              {job.application_status ? (
                <Badge variant="secondary">{titleCase(job.application_status.toLowerCase())}</Badge>
              ) : null}
              {match?.user_decision ? (
                <Badge variant={match.user_decision === "approve" ? "success" : "secondary"}>
                  {match.user_decision === "approve" ? "Approved" : "Skipped"}
                </Badge>
              ) : null}
            </div>

            <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted-foreground">
              <span className="flex items-center gap-1">
                <Building2 className="h-3.5 w-3.5" aria-hidden />
                {job.company_name}
              </span>
              <span className="flex items-center gap-1">
                <MapPin className="h-3.5 w-3.5" aria-hidden />
                {job.location ?? "Location not stated"}
              </span>
              <span>{titleCase(job.remote_type)}</span>
              {salary ? <span className="tabular">{salary}</span> : null}
              {job.detected_ats ? <span>{titleCase(job.detected_ats)}</span> : null}
            </div>

            <div className="mt-2 flex flex-wrap gap-1.5">
              <Badge variant={sponsorship.variant}>{sponsorship.text}</Badge>
              {match?.matched_skills.slice(0, 6).map((skill) => (
                <Badge key={skill} variant="success">
                  {skill}
                </Badge>
              ))}
              {match?.missing_skills.slice(0, 4).map((skill) => (
                <Badge key={skill} variant="outline">
                  {skill}
                </Badge>
              ))}
            </div>

            {match?.explanation ? (
              <p className="mt-2 text-sm text-muted-foreground">{match.explanation}</p>
            ) : (
              <p className="mt-2 text-sm text-muted-foreground">
                Not scored yet — open the job to score it against your profile.
              </p>
            )}

            {match?.hard_requirement_failed ? (
              <Alert variant="warning" className="mt-3 py-2">
                <p className="text-xs">
                  {match.risks[0] ?? "This job fails one of your hard requirements."}
                </p>
              </Alert>
            ) : null}
          </div>

          <div className="flex shrink-0 flex-col items-center gap-3">
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
              <Button
                size="sm"
                variant="ghost"
                disabled={decide.isPending}
                onClick={() => decide.mutate("skip")}
              >
                Skip
              </Button>
              {job.apply_url ? (
                <Button asChild size="sm" variant="ghost">
                  <a href={job.apply_url} target="_blank" rel="noreferrer">
                    <ExternalLink className="h-3.5 w-3.5" aria-hidden />
                    Open
                  </a>
                </Button>
              ) : null}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
