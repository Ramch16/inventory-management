"use client";

import { CheckCircle2, Circle, PauseCircle } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import type { ProfileReadiness } from "@/lib/api/types";

interface ReadinessCardProps {
  readiness: ProfileReadiness;
}

export function ReadinessCard({ readiness }: ReadinessCardProps) {
  const checks = [
    { label: "Profile complete", done: readiness.profile_score === 100 },
    { label: "Master resume uploaded", done: readiness.has_master_resume },
    { label: "Work authorization declared", done: readiness.work_authorization_declared },
    { label: "Automation enabled", done: readiness.automation_enabled },
  ];

  const setupFinished =
    readiness.profile_score === 100 &&
    readiness.has_master_resume &&
    readiness.work_authorization_declared;

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between gap-4">
          <div>
            <CardTitle>Getting ready</CardTitle>
            <CardDescription>
              Automated submission stays off until each of these is true.
            </CardDescription>
          </div>
          {readiness.automation_paused ? (
            <span className="flex items-center gap-1.5 whitespace-nowrap text-xs font-medium text-warning">
              <PauseCircle className="h-3.5 w-3.5" aria-hidden />
              Paused
            </span>
          ) : null}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div>
          <div className="mb-1.5 flex items-center justify-between text-xs text-muted-foreground">
            <span>Profile completeness</span>
            <span className="tabular">{readiness.profile_score}%</span>
          </div>
          <Progress value={readiness.profile_score} />
        </div>

        <ul className="space-y-2">
          {checks.map((check) => (
            <li key={check.label} className="flex items-center gap-2 text-sm">
              {check.done ? (
                <CheckCircle2 className="h-4 w-4 shrink-0 text-success" aria-hidden />
              ) : (
                <Circle className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
              )}
              <span className={check.done ? "text-muted-foreground line-through" : undefined}>
                {check.label}
              </span>
            </li>
          ))}
        </ul>

        {readiness.blockers.length > 0 ? (
          <div className="rounded-md bg-muted/60 p-3">
            <p className="text-xs font-medium">What is left</p>
            <ul className="mt-1.5 space-y-1 text-xs text-muted-foreground">
              {readiness.blockers.map((blocker) => (
                <li key={blocker}>· {blocker}</li>
              ))}
            </ul>
          </div>
        ) : null}

        <div className="flex flex-wrap gap-2">
          {setupFinished ? (
            <Button asChild size="sm">
              <Link href="/profile">Edit profile</Link>
            </Button>
          ) : (
            // While anything is outstanding the guided route is the useful one: it
            // shows every step at once instead of one page at a time.
            <Button asChild size="sm">
              <Link href="/onboarding">Continue setup</Link>
            </Button>
          )}
          {!readiness.has_master_resume ? (
            <Button asChild size="sm" variant="outline">
              <Link href="/resume">Upload resume</Link>
            </Button>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
}
