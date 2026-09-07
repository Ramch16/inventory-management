"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Check, CircleDashed, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { ApiError } from "@/lib/api/client";
import { endpoints, queryKeys } from "@/lib/api/queries";
import type { OnboardingStatus } from "@/lib/api/types";

interface Step {
  /** Matches a key of the `sections` map the API returns, or "resume". */
  key: string;
  title: string;
  description: string;
  href: string;
  action: string;
  /** True when nothing may be submitted until this step is done. */
  blocking: boolean;
}

const STEPS: Step[] = [
  {
    key: "resume",
    title: "Upload your master resume",
    description:
      "Everything a tailored resume can say comes from this document and from your profile. Nothing is invented to fill a gap.",
    href: "/resume",
    action: "Upload a resume",
    blocking: true,
  },
  {
    key: "identity",
    title: "Confirm your contact details",
    description:
      "Name, e-mail, phone and location are written onto every application form, so they have to be right before anything is sent.",
    href: "/profile",
    action: "Edit profile",
    blocking: true,
  },
  {
    key: "professional",
    title: "Add your current title and years of experience",
    description: "Job matching compares these against each posting's requirements.",
    href: "/profile",
    action: "Edit profile",
    blocking: false,
  },
  {
    key: "experience",
    title: "Confirm your work history",
    description:
      "Imported positions are yours to correct. Tailoring may only draw on experience you have entered or approved.",
    href: "/profile",
    action: "Review experience",
    blocking: true,
  },
  {
    key: "education",
    title: "Confirm your education",
    description: "Degrees and institutions are used verbatim; none are added on your behalf.",
    href: "/profile",
    action: "Review education",
    blocking: false,
  },
  {
    key: "skills",
    title: "Verify your skills",
    description:
      "Skills imported from a resume arrive unverified. Confirming them is what allows a tailored resume to mention them.",
    href: "/profile",
    action: "Review skills",
    blocking: true,
  },
  {
    key: "authorization",
    title: "Declare your work authorization",
    description:
      "Answers about the right to work, sponsorship and clearances are never inferred from a resume. You state them once, here, and they are reused exactly as written.",
    href: "/profile",
    action: "Declare authorization",
    blocking: true,
  },
];

function stepDone(status: OnboardingStatus, step: Step): boolean {
  if (step.key === "resume") return status.has_master_resume;
  return status.sections[step.key] ?? false;
}

function StepRow({ step, done, index }: { step: Step; done: boolean; index: number }) {
  return (
    <li className="flex gap-4 border-b py-4 last:border-b-0">
      <div
        className={`mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border text-xs font-medium ${
          done ? "border-success/40 bg-success/10 text-success" : "text-muted-foreground"
        }`}
        aria-hidden
      >
        {done ? <Check className="h-4 w-4" /> : index + 1}
      </div>
      <div className="flex-1 space-y-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm font-medium">{step.title}</span>
          {done ? (
            <Badge variant="success">Done</Badge>
          ) : step.blocking ? (
            <Badge variant="warning">Required</Badge>
          ) : (
            <Badge variant="outline">Recommended</Badge>
          )}
        </div>
        <p className="text-sm text-muted-foreground">{step.description}</p>
      </div>
      <div className="self-center">
        <Button asChild variant={done ? "ghost" : "outline"} size="sm">
          <Link href={step.href}>
            {done ? "Review" : step.action}
            <ArrowRight className="ml-1.5 h-3.5 w-3.5" aria-hidden />
          </Link>
        </Button>
      </div>
    </li>
  );
}

export default function OnboardingPage() {
  const queryClient = useQueryClient();
  const router = useRouter();
  const { toast } = useToast();
  const [confirmed, setConfirmed] = useState(false);

  const onboarding = useQuery({ queryKey: queryKeys.onboarding, queryFn: endpoints.onboarding });

  const complete = useMutation({
    mutationFn: endpoints.completeOnboarding,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.onboarding });
      queryClient.invalidateQueries({ queryKey: queryKeys.session });
      toast({
        title: "Profile confirmed",
        description: "You can now turn automation on from Settings.",
        variant: "success",
      });
      router.push("/settings");
    },
    onError: (error) =>
      toast({
        title: "Not ready yet",
        description: error instanceof ApiError ? error.message : "Something went wrong.",
        variant: "error",
      }),
  });

  if (onboarding.isLoading || !onboarding.data) {
    return (
      <div className="mx-auto max-w-3xl space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  const status = onboarding.data;
  const done = STEPS.filter((step) => stepDone(status, step)).length;
  const percent = Math.round((100 * done) / STEPS.length);
  const alreadyCompleted = Boolean(status.completed_at);
  const ready = status.ready_for_automation && status.has_master_resume;

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Set up your account</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Seven steps between an empty account and applications the platform can send on your
          behalf. Work through them in any order.
        </p>
      </div>

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <CardTitle>
                {done} of {STEPS.length} complete
              </CardTitle>
              <CardDescription>
                {ready
                  ? "Everything required is in place."
                  : "Automated submission stays off until the required steps are done."}
              </CardDescription>
            </div>
            <Badge variant={ready ? "success" : "warning"}>{percent}%</Badge>
          </div>
        </CardHeader>
        <CardContent>
          <Progress value={percent} />
          <ul className="mt-2">
            {STEPS.map((step, index) => (
              <StepRow
                key={step.key}
                step={step}
                index={index}
                done={stepDone(status, step)}
              />
            ))}
          </ul>
        </CardContent>
      </Card>

      <Card className={alreadyCompleted ? "border-success/40" : undefined}>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ShieldCheck className="h-4 w-4" aria-hidden />
            Confirm your profile
          </CardTitle>
          <CardDescription>
            The last step is your own confirmation. Until you give it, nothing is submitted to an
            employer — no matter how the automation settings are configured.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {alreadyCompleted ? (
            <Alert variant="success" className="flex items-start gap-2">
              <Check className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
              <div>
                You confirmed your profile on{" "}
                {new Date(status.completed_at as string).toLocaleDateString()}. Turn automation on
                from <Link href="/settings" className="underline">Settings</Link>, or start
                applying from <Link href="/jobs" className="underline">Jobs</Link>.
              </div>
            </Alert>
          ) : (
            <>
              {status.blocks_automation.length > 0 ? (
                <Alert variant="warning" className="flex items-start gap-2">
                  <CircleDashed className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
                  <div className="space-y-1">
                    <p className="font-medium">Still outstanding</p>
                    <ul className="list-disc space-y-0.5 pl-4">
                      {status.blocks_automation.map((blocker) => (
                        <li key={blocker}>{blocker}</li>
                      ))}
                    </ul>
                  </div>
                </Alert>
              ) : null}

              <label className="flex items-start gap-2 text-sm">
                <input
                  type="checkbox"
                  className="mt-0.5 h-4 w-4 rounded border-input"
                  checked={confirmed}
                  disabled={!ready}
                  onChange={(event) => setConfirmed(event.target.checked)}
                />
                I confirm that everything in my profile is accurate, and that the answers it holds
                may be used to complete application forms on my behalf.
              </label>

              <Button
                disabled={!ready || !confirmed || complete.isPending}
                onClick={() => complete.mutate()}
              >
                {complete.isPending ? "Confirming…" : "Confirm and finish setup"}
              </Button>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
