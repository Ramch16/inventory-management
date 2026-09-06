"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { PauseCircle, PlayCircle } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { useToast } from "@/components/ui/toast";
import { ApiError } from "@/lib/api/client";
import { endpoints, queryKeys } from "@/lib/api/queries";
import type { AutomationSettings, ResumeTemplate } from "@/lib/api/types";

const TEMPLATES: Array<{ value: ResumeTemplate; label: string }> = [
  { value: "ats_classic", label: "ATS Classic" },
  { value: "modern_professional", label: "Modern Professional" },
  { value: "technical", label: "Technical" },
  { value: "minimal", label: "Minimal" },
];

function Toggle({
  id,
  label,
  description,
  checked,
  onChange,
  disabled,
}: {
  id: string;
  label: string;
  description: string;
  checked: boolean;
  onChange: (value: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <div className="flex items-start justify-between gap-4 py-3">
      <div>
        <label htmlFor={id} className="text-sm font-medium">
          {label}
        </label>
        <p className="mt-0.5 text-xs text-muted-foreground">{description}</p>
      </div>
      <Switch id={id} checked={checked} onCheckedChange={onChange} disabled={disabled} />
    </div>
  );
}

export function AutomationSettingsPanel() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [draft, setDraft] = useState<AutomationSettings | null>(null);

  const settings = useQuery({
    queryKey: queryKeys.automationSettings,
    queryFn: endpoints.automationSettings,
  });
  const onboarding = useQuery({ queryKey: queryKeys.onboarding, queryFn: endpoints.onboarding });

  useEffect(() => {
    if (settings.data) setDraft(settings.data);
  }, [settings.data]);

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: queryKeys.automationSettings });
    queryClient.invalidateQueries({ queryKey: queryKeys.dashboard });
    queryClient.invalidateQueries({ queryKey: queryKeys.session });
  };

  const save = useMutation({
    mutationFn: (payload: Partial<AutomationSettings>) =>
      endpoints.updateAutomationSettings(payload),
    onSuccess: (updated) => {
      setDraft(updated);
      invalidate();
      toast({ title: "Automation settings saved", variant: "success" });
    },
    onError: (error) =>
      toast({
        title: "Could not save",
        description: error instanceof ApiError ? error.message : "Something went wrong.",
        variant: "error",
      }),
  });

  const pause = useMutation({
    mutationFn: (paused: boolean) => endpoints.setPause(paused),
    onSuccess: (updated) => {
      setDraft(updated);
      invalidate();
    },
  });

  const completeOnboarding = useMutation({
    mutationFn: endpoints.completeOnboarding,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.onboarding });
      toast({ title: "Profile confirmed", variant: "success" });
    },
    onError: (error) =>
      toast({
        title: "Not ready yet",
        description: error instanceof ApiError ? error.message : "Something went wrong.",
        variant: "error",
      }),
  });

  if (!draft) return null;

  const onboardingDone = Boolean(onboarding.data?.completed_at);

  return (
    <div className="space-y-6">
      <Card className={draft.automation_paused ? "border-warning/50" : undefined}>
        <CardHeader>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <CardTitle>Automation</CardTitle>
              <CardDescription>
                One switch stops everything, including work already queued.
              </CardDescription>
            </div>
            <Badge variant={draft.automation_paused ? "warning" : "success"}>
              {draft.automation_paused ? "Paused" : "Running"}
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <Button
            variant={draft.automation_paused ? "default" : "destructive"}
            onClick={() => pause.mutate(!draft.automation_paused)}
            disabled={pause.isPending}
          >
            {draft.automation_paused ? (
              <>
                <PlayCircle className="h-4 w-4" aria-hidden />
                Resume all applications
              </>
            ) : (
              <>
                <PauseCircle className="h-4 w-4" aria-hidden />
                Pause all applications
              </>
            )}
          </Button>

          {!onboardingDone ? (
            <Alert variant="warning">
              <p className="text-sm font-medium">
                Confirm your profile before enabling automation.
              </p>
              <p className="mt-1 text-sm text-muted-foreground">
                Nothing is submitted on your behalf until you confirm that the information
                an employer will see is accurate.
              </p>
              {onboarding.data && !onboarding.data.ready_for_automation ? (
                <ul className="mt-2 space-y-1 text-xs text-muted-foreground">
                  {onboarding.data.blocks_automation.map((item) => (
                    <li key={item}>· {item}</li>
                  ))}
                  {onboarding.data.has_master_resume ? null : (
                    <li>· Upload a master resume.</li>
                  )}
                </ul>
              ) : null}
              <div className="mt-3 flex gap-2">
                <Button
                  size="sm"
                  onClick={() => completeOnboarding.mutate()}
                  disabled={completeOnboarding.isPending}
                >
                  My profile is accurate
                </Button>
                <Button asChild size="sm" variant="outline">
                  <Link href="/profile">Review profile</Link>
                </Button>
              </div>
            </Alert>
          ) : null}

          <div className="divide-y">
            <Toggle
              id="enabled"
              label="Automation enabled"
              description="Discovery and applications run on your behalf."
              checked={draft.enabled}
              disabled={!onboardingDone}
              onChange={(value) => save.mutate({ enabled: value })}
            />
            <Toggle
              id="require_review"
              label="Review before submitting"
              description="Fill the form, then wait for you to look before anything is sent."
              checked={draft.require_review_before_submit}
              onChange={(value) => save.mutate({ require_review_before_submit: value })}
            />
            <Toggle
              id="auto_submit"
              label="Submit automatically"
              description="Only applies when review-before-submit is off, and never when a step needs a person."
              checked={draft.auto_submit_enabled}
              onChange={(value) => save.mutate({ auto_submit_enabled: value })}
            />
            <Toggle
              id="cover_letters"
              label="Generate cover letters"
              description="Written from your approved records, and dropped if they cannot be verified."
              checked={draft.generate_cover_letters}
              onChange={(value) => save.mutate({ generate_cover_letters: value })}
            />
            <Toggle
              id="browser_verification"
              label="Allow browser verification"
              description="Hold the page open so you can complete a CAPTCHA or a code yourself."
              checked={draft.allow_browser_verification}
              onChange={(value) => save.mutate({ allow_browser_verification: value })}
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Limits and quality</CardTitle>
          <CardDescription>
            Caps protect your own reputation and stop runaway automation. They are not a
            way around an employer&apos;s limits.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form
            className="grid gap-4 sm:grid-cols-2"
            onSubmit={(event) => {
              event.preventDefault();
              save.mutate({
                daily_application_limit: draft.daily_application_limit,
                hourly_application_limit: draft.hourly_application_limit,
                min_delay_seconds: draft.min_delay_seconds,
                max_delay_seconds: draft.max_delay_seconds,
                min_match_score: draft.min_match_score,
                default_resume_template: draft.default_resume_template,
                resume_max_pages: draft.resume_max_pages,
              });
            }}
          >
            {[
              ["daily_application_limit", "Applications per day", 1, 100],
              ["hourly_application_limit", "Applications per hour", 1, 25],
              ["min_delay_seconds", "Minimum delay (seconds)", 0, 3600],
              ["max_delay_seconds", "Maximum delay (seconds)", 0, 7200],
              ["min_match_score", "Minimum match score", 0, 100],
              ["resume_max_pages", "Resume pages", 1, 3],
            ].map(([key, label, min, max]) => (
              <div key={key as string} className="space-y-1.5">
                <label htmlFor={key as string} className="text-sm font-medium">
                  {label as string}
                </label>
                <Input
                  id={key as string}
                  type="number"
                  min={min as number}
                  max={max as number}
                  value={String(draft[key as keyof AutomationSettings] ?? "")}
                  onChange={(event) =>
                    setDraft({ ...draft, [key as string]: Number(event.target.value) })
                  }
                />
              </div>
            ))}

            <div className="space-y-1.5">
              <label htmlFor="default_resume_template" className="text-sm font-medium">
                Default resume template
              </label>
              <Select
                id="default_resume_template"
                value={draft.default_resume_template}
                onChange={(event) =>
                  setDraft({
                    ...draft,
                    default_resume_template: event.target.value as ResumeTemplate,
                  })
                }
              >
                {TEMPLATES.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </Select>
            </div>

            <div className="flex items-end justify-end sm:col-span-2">
              <Button type="submit" disabled={save.isPending}>
                {save.isPending ? "Saving…" : "Save limits"}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
