"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, ArrowLeft, CheckCircle2, ShieldQuestion } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { StatusBadge } from "@/components/applications/status-badge";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { ApiError } from "@/lib/api/client";
import { endpoints, queryKeys } from "@/lib/api/queries";
import { formatDateTime, titleCase } from "@/lib/utils";

const MANUAL_STATUSES = ["INTERVIEW", "ASSESSMENT", "REJECTED", "OFFER", "WITHDRAWN"];

export default function ApplicationDetailPage() {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const application = useQuery({
    queryKey: queryKeys.application(id),
    queryFn: () => endpoints.application(id),
    refetchInterval: (query) =>
      query.state.data?.status === "APPLICATION_STARTING" ? 5_000 : false,
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: queryKeys.application(id) });
    queryClient.invalidateQueries({ queryKey: ["applications"] });
  };

  const start = useMutation({
    mutationFn: () => endpoints.startApplication(id),
    onSuccess: () => {
      invalidate();
      toast({ title: "Queued for the automation worker", variant: "success" });
    },
    onError: (error) =>
      toast({
        title: "Could not start",
        description: error instanceof ApiError ? error.message : "Something went wrong.",
        variant: "error",
      }),
  });

  const cancel = useMutation({
    mutationFn: () => endpoints.cancelApplication(id),
    onSuccess: invalidate,
  });

  const setStatus = useMutation({
    mutationFn: (status: string) => endpoints.updateApplicationStatus(id, status),
    onSuccess: invalidate,
    onError: (error) =>
      toast({
        title: "Status not allowed",
        description: error instanceof ApiError ? error.message : "Something went wrong.",
        variant: "error",
      }),
  });

  if (application.isLoading || !application.data) {
    return <Skeleton className="h-96 w-full max-w-4xl" />;
  }

  const detail = application.data;
  const sensitiveQuestions = detail.questions.filter((question) => question.is_sensitive);

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <Link
        href="/applications"
        className="inline-flex items-center gap-1 text-sm text-muted-foreground underline-offset-4 hover:underline"
      >
        <ArrowLeft className="h-3.5 w-3.5" aria-hidden />
        Back to applications
      </Link>

      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{detail.title}</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {detail.company_name}
            {detail.detected_ats ? ` · ${titleCase(detail.detected_ats)}` : ""}
            {detail.match_score !== null ? ` · ${detail.match_score}% match` : ""}
          </p>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <StatusBadge status={detail.status} />
            {detail.auto_submit ? (
              <Badge variant="secondary">Auto-submit</Badge>
            ) : (
              <Badge variant="outline">Review before submit</Badge>
            )}
            {detail.attempts > 0 ? (
              <span className="text-xs text-muted-foreground">
                Attempt {detail.attempts}
              </span>
            ) : null}
          </div>
        </div>
        <div className="flex flex-col gap-2">
          {["APPROVED", "RESUME_READY", "FAILED"].includes(detail.status) ? (
            <Button onClick={() => start.mutate()} disabled={start.isPending}>
              {start.isPending ? "Queueing…" : detail.attempts > 0 ? "Retry" : "Start application"}
            </Button>
          ) : null}
          {detail.open_interventions > 0 ? (
            <Button asChild variant="outline">
              <Link href="/interventions">Resolve {detail.open_interventions} item(s)</Link>
            </Button>
          ) : null}
          {!["SUBMITTED", "CONFIRMATION_CAPTURED", "CANCELLED"].includes(detail.status) ? (
            <Button variant="ghost" onClick={() => cancel.mutate()} disabled={cancel.isPending}>
              Cancel
            </Button>
          ) : null}
        </div>
      </div>

      {detail.status === "SUBMISSION_UNCONFIRMED" ? (
        <Alert variant="warning">
          <div className="flex gap-2">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
            <p className="text-sm">
              The form was submitted but no confirmation appeared, so this is recorded as
              unconfirmed rather than applied. Check your e-mail before applying again.
            </p>
          </div>
        </Alert>
      ) : null}

      {detail.confirmation_id ? (
        <Alert variant="success">
          <div className="flex gap-2">
            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
            <p className="text-sm">
              Confirmed by the employer. Reference {detail.confirmation_id}.
            </p>
          </div>
        </Alert>
      ) : null}

      {detail.failure_detail ? (
        <Alert variant="destructive">
          <p className="text-sm font-medium">
            {titleCase((detail.failure_reason ?? "failed").toLowerCase())}
          </p>
          <p className="mt-1 text-sm text-muted-foreground">{detail.failure_detail}</p>
        </Alert>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>Record an outcome</CardTitle>
          <CardDescription>
            You can record what happened after applying. Submission itself is only ever
            recorded when the automation observes it.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="w-64">
            <Select
              aria-label="Record an outcome"
              value=""
              onChange={(event) => event.target.value && setStatus.mutate(event.target.value)}
            >
              <option value="">Choose an outcome…</option>
              {MANUAL_STATUSES.map((value) => (
                <option key={value} value={value}>
                  {titleCase(value.toLowerCase())}
                </option>
              ))}
            </Select>
          </div>
        </CardContent>
      </Card>

      {detail.questions.length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>Application questions</CardTitle>
            <CardDescription>
              What was asked, what was answered, and where each answer came from.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ul className="divide-y">
              {detail.questions.map((question) => (
                <li key={question.id} className="py-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="text-sm font-medium">
                      {question.question ?? question.label ?? question.field_id}
                    </p>
                    {question.required ? <Badge variant="outline">Required</Badge> : null}
                    {question.is_sensitive ? (
                      <Badge variant="warning">
                        <ShieldQuestion className="mr-1 h-3 w-3" aria-hidden />
                        Sensitive
                      </Badge>
                    ) : null}
                  </div>
                  <p className="mt-1 text-sm text-muted-foreground">
                    {question.answer ?? "— not answered —"}
                  </p>
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    {question.source ? `${titleCase(question.source)} · ` : ""}
                    confidence {question.confidence.toFixed(2)}
                    {question.requires_review ? " · awaiting your review" : ""}
                    {question.reason ? ` · ${question.reason}` : ""}
                  </p>
                </li>
              ))}
            </ul>
            {sensitiveQuestions.length > 0 ? (
              <p className="mt-3 text-xs text-muted-foreground">
                Sensitive questions are answered only from fields you filled in yourself, or
                left for you.
              </p>
            ) : null}
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>Timeline</CardTitle>
        </CardHeader>
        <CardContent>
          <ol className="space-y-3">
            {detail.steps.map((step) => (
              <li key={step.id} className="flex gap-3 text-sm">
                <span className="w-40 shrink-0 text-xs text-muted-foreground">
                  {formatDateTime(step.created_at)}
                </span>
                <span className="flex-1">
                  <span className="font-medium">{titleCase(step.name)}</span>
                  <Badge
                    variant={
                      step.status === "ok"
                        ? "success"
                        : step.status === "paused"
                          ? "warning"
                          : step.status === "failed"
                            ? "destructive"
                            : "secondary"
                    }
                    className="ml-2"
                  >
                    {step.status}
                  </Badge>
                  {step.message ? (
                    <span className="mt-0.5 block text-muted-foreground">{step.message}</span>
                  ) : null}
                </span>
              </li>
            ))}
          </ol>
        </CardContent>
      </Card>

      {detail.logs.length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>Automation log</CardTitle>
            <CardDescription>
              Structured events from the run. Credentials and one-time codes are never
              recorded.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2 text-xs">
              {detail.logs.map((log) => (
                <li key={log.id} className="flex gap-3">
                  <span className="w-40 shrink-0 text-muted-foreground">
                    {formatDateTime(log.created_at)}
                  </span>
                  <span className="flex-1">
                    <span className="font-medium">{log.event}</span>
                    {log.status ? ` · ${log.status}` : ""}
                    {log.message ? (
                      <span className="block text-muted-foreground">{log.message}</span>
                    ) : null}
                  </span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}
