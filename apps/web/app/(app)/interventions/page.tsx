"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ExternalLink, ShieldAlert, TriangleAlert } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import { ApiError } from "@/lib/api/client";
import { endpoints, queryKeys } from "@/lib/api/queries";
import type { Intervention } from "@/lib/api/types";
import { formatDateTime, titleCase } from "@/lib/utils";

const EXPLANATIONS: Record<string, string> = {
  captcha:
    "This employer uses a CAPTCHA. JobApply does not solve CAPTCHAs — open the page, complete it yourself, then continue.",
  mfa: "This step needs multi-factor authentication, which only you can complete.",
  otp: "A one-time code was sent to you. Enter it below; it is used once and never stored.",
  authentication_required:
    "This employer requires an account before applying. Sign in yourself, or cancel this application.",
  legal_attestation:
    "This form asks you to certify something. Only you can agree to it, so it is never answered automatically.",
  missing_data: "Some questions could not be answered from your profile.",
  low_confidence: "Some answers were not confident enough to send without your review.",
  unsupported_form: "This application flow is not one the platform can complete on its own.",
};

function InterventionCard({ item }: { item: Intervention }) {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [otp, setOtp] = useState("");

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["interventions"] });
    queryClient.invalidateQueries({ queryKey: ["applications"] });
    queryClient.invalidateQueries({ queryKey: queryKeys.dashboard });
  };

  const proceed = useMutation({
    mutationFn: () =>
      endpoints.continueIntervention(item.id, {
        answers: Object.keys(answers).length ? answers : undefined,
        otp_code: otp || undefined,
      }),
    onSuccess: () => {
      invalidate();
      toast({ title: "Continuing the application", variant: "success" });
    },
    onError: (error) =>
      toast({
        title: "Could not continue",
        description: error instanceof ApiError ? error.message : "Something went wrong.",
        variant: "error",
      }),
  });

  const cancel = useMutation({
    mutationFn: () => endpoints.cancelIntervention(item.id),
    onSuccess: invalidate,
  });

  const questions = item.payload?.questions ?? [];
  const needsOtp = item.type === "otp";

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <CardTitle className="text-base">
              {item.title} · {item.company_name}
            </CardTitle>
            <CardDescription>
              {item.current_step ? `Step: ${item.current_step} · ` : ""}
              {formatDateTime(item.created_at)}
            </CardDescription>
          </div>
          <Badge variant="warning">{titleCase(item.type)}</Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <Alert variant="info">
          <div className="flex gap-2">
            <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
            <div className="text-sm">
              <p>{item.reason}</p>
              {EXPLANATIONS[item.type] ? (
                <p className="mt-1 text-muted-foreground">{EXPLANATIONS[item.type]}</p>
              ) : null}
            </div>
          </div>
        </Alert>

        {item.screenshot_url ? (
          <a href={item.screenshot_url} target="_blank" rel="noreferrer" className="block">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={item.screenshot_url}
              alt="What the automation saw when it stopped"
              className="max-h-80 w-full rounded-md border object-cover object-top"
            />
          </a>
        ) : null}

        {item.page_url ? (
          <Button asChild variant="outline" size="sm">
            <a href={item.page_url} target="_blank" rel="noreferrer">
              <ExternalLink className="h-3.5 w-3.5" aria-hidden />
              Open the page
            </a>
          </Button>
        ) : null}

        {needsOtp ? (
          <div className="w-52 space-y-1.5">
            <label htmlFor={`otp-${item.id}`} className="text-sm font-medium">
              Verification code
            </label>
            <Input
              id={`otp-${item.id}`}
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={16}
              value={otp}
              onChange={(event) => setOtp(event.target.value)}
            />
            <p className="text-xs text-muted-foreground">Used once, never stored.</p>
          </div>
        ) : null}

        {questions.length > 0 ? (
          <div className="space-y-4">
            {questions.map((question) => (
              <div key={question.field_id} className="space-y-1.5">
                <label
                  htmlFor={`answer-${item.id}-${question.field_id}`}
                  className="text-sm font-medium"
                >
                  {question.question ?? question.field_id}
                  {question.is_sensitive ? (
                    <Badge variant="warning" className="ml-2">
                      Only you can answer this
                    </Badge>
                  ) : null}
                </label>
                {question.options && question.options.length > 0 ? (
                  <Select
                    id={`answer-${item.id}-${question.field_id}`}
                    value={answers[question.field_id] ?? question.draft ?? ""}
                    onChange={(event) =>
                      setAnswers({ ...answers, [question.field_id]: event.target.value })
                    }
                  >
                    <option value="">Choose…</option>
                    {question.options.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </Select>
                ) : (
                  <Textarea
                    id={`answer-${item.id}-${question.field_id}`}
                    rows={3}
                    value={answers[question.field_id] ?? question.draft ?? ""}
                    onChange={(event) =>
                      setAnswers({ ...answers, [question.field_id]: event.target.value })
                    }
                  />
                )}
                {question.reason ? (
                  <p className="text-xs text-muted-foreground">{question.reason}</p>
                ) : null}
              </div>
            ))}
          </div>
        ) : null}

        <div className="flex flex-wrap gap-2">
          <Button onClick={() => proceed.mutate()} disabled={proceed.isPending}>
            {proceed.isPending ? "Continuing…" : "Continue"}
          </Button>
          <Button variant="ghost" onClick={() => cancel.mutate()} disabled={cancel.isPending}>
            Cancel this application
          </Button>
          <Button asChild variant="ghost">
            <Link href={`/applications/${item.application_id}`}>View application</Link>
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

export default function InterventionsPage() {
  const [status, setStatus] = useState("open");
  const interventions = useQuery({
    queryKey: queryKeys.interventions(status),
    queryFn: () => endpoints.interventions(status),
    refetchInterval: 30_000,
  });

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Needs your attention</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Applications paused because a person is genuinely required.
          </p>
        </div>
        <div className="w-40">
          <Select value={status} onChange={(event) => setStatus(event.target.value)}>
            <option value="open">Open</option>
            <option value="resolved">Resolved</option>
            <option value="cancelled">Cancelled</option>
          </Select>
        </div>
      </div>

      {interventions.isLoading ? (
        <Skeleton className="h-64 w-full" />
      ) : (interventions.data?.items.length ?? 0) === 0 ? (
        <EmptyState
          icon={TriangleAlert}
          title={status === "open" ? "Nothing is waiting on you" : "Nothing here"}
          description={
            status === "open"
              ? "When an application hits a CAPTCHA, a verification code, a legal question or anything ambiguous, it appears here with a screenshot and a Continue button."
              : undefined
          }
        />
      ) : (
        <div className="space-y-4">
          {interventions.data?.items.map((item) => (
            <InterventionCard key={item.id} item={item} />
          ))}
        </div>
      )}
    </div>
  );
}
