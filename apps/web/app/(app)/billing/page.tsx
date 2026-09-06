"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check } from "lucide-react";

import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { ApiError } from "@/lib/api/client";
import { endpoints, queryKeys } from "@/lib/api/queries";
import { formatNumber, titleCase } from "@/lib/utils";

export default function BillingPage() {
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const billing = useQuery({ queryKey: queryKeys.billing, queryFn: endpoints.billing });

  const changePlan = useMutation({
    mutationFn: (plan: string) => endpoints.changePlan(plan),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.billing });
      toast({ title: "Plan updated", variant: "success" });
    },
    onError: (error) => {
      const details =
        error instanceof ApiError ? (error.details as { checkout_url?: string }) : undefined;
      if (details?.checkout_url) {
        window.location.href = details.checkout_url;
        return;
      }
      toast({
        title: "Could not change plan",
        description: error instanceof ApiError ? error.message : "Something went wrong.",
        variant: "error",
      });
    },
  });

  if (billing.isLoading || !billing.data) {
    return <Skeleton className="h-96 w-full max-w-4xl" />;
  }

  const state = billing.data;
  const used = state.usage.applications_limit
    ? (state.usage.applications_submitted / state.usage.applications_limit) * 100
    : 0;

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Billing</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Your plan and what you have used this month.
        </p>
      </div>

      {!state.checkout_available ? (
        <Alert variant="info">
          <p className="text-sm">
            No payment provider is configured on this deployment, so plans can be changed
            freely and nothing is ever charged. The limits below are still enforced.
          </p>
        </Alert>
      ) : null}

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <CardTitle>Usage this month</CardTitle>
              <CardDescription>Period {state.usage.period}</CardDescription>
            </div>
            <Badge variant="success">{titleCase(state.plan)} plan</Badge>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-semibold tabular">
              {formatNumber(state.usage.applications_submitted)}
            </span>
            <span className="text-sm text-muted-foreground">
              of {formatNumber(state.usage.applications_limit)} applications
            </span>
          </div>
          <Progress value={used} />
          <p className="text-xs text-muted-foreground">
            {formatNumber(state.usage.remaining)} remaining in this period.
          </p>
        </CardContent>
      </Card>

      <div className="grid gap-4 sm:grid-cols-3">
        {state.plans.map((plan) => (
          <Card key={plan.plan} className={plan.current ? "border-primary" : undefined}>
            <CardHeader>
              <div className="flex items-center justify-between gap-2">
                <CardTitle className="text-base">{titleCase(plan.plan)}</CardTitle>
                {plan.current ? <Badge variant="default">Current</Badge> : null}
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              <ul className="space-y-1.5 text-sm">
                <li className="flex items-center gap-2">
                  <Check className="h-3.5 w-3.5 text-success" aria-hidden />
                  {formatNumber(plan.applications_per_day)} applications a day
                </li>
                <li className="flex items-center gap-2">
                  <Check className="h-3.5 w-3.5 text-success" aria-hidden />
                  {formatNumber(plan.applications_per_month)} a month
                </li>
                <li className="flex items-center gap-2">
                  <Check
                    className={
                      plan.ai_tailoring
                        ? "h-3.5 w-3.5 text-success"
                        : "h-3.5 w-3.5 text-muted-foreground/40"
                    }
                    aria-hidden
                  />
                  <span className={plan.ai_tailoring ? undefined : "text-muted-foreground"}>
                    AI resume tailoring
                  </span>
                </li>
                <li className="flex items-center gap-2">
                  <Check
                    className={
                      plan.cover_letters
                        ? "h-3.5 w-3.5 text-success"
                        : "h-3.5 w-3.5 text-muted-foreground/40"
                    }
                    aria-hidden
                  />
                  <span className={plan.cover_letters ? undefined : "text-muted-foreground"}>
                    Cover letters
                  </span>
                </li>
              </ul>
              <Button
                className="w-full"
                variant={plan.current ? "outline" : "default"}
                disabled={plan.current || changePlan.isPending}
                onClick={() => changePlan.mutate(plan.plan)}
              >
                {plan.current ? "Your plan" : `Switch to ${titleCase(plan.plan)}`}
              </Button>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
