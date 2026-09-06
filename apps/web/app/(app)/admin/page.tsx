"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ShieldCheck } from "lucide-react";

import { StatCard } from "@/components/dashboard/stat-card";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useSession } from "@/hooks/use-session";
import { ApiError } from "@/lib/api/client";
import { endpoints, queryKeys } from "@/lib/api/queries";
import { formatDate, formatNumber, formatPercent, titleCase } from "@/lib/utils";

export default function AdminPage() {
  const queryClient = useQueryClient();
  const { data: user } = useSession();

  const overview = useQuery({
    queryKey: queryKeys.adminOverview,
    queryFn: endpoints.adminOverview,
    enabled: user?.role === "admin",
    retry: false,
  });
  const users = useQuery({
    queryKey: queryKeys.adminUsers,
    queryFn: endpoints.adminUsers,
    enabled: user?.role === "admin",
    retry: false,
  });

  const disable = useMutation({
    mutationFn: (id: string) => endpoints.adminDisableUser(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.adminUsers }),
  });

  if (user?.role !== "admin") {
    return (
      <div className="mx-auto max-w-2xl">
        <Alert variant="warning">
          <div className="flex gap-2">
            <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
            <p className="text-sm">This area is for administrators.</p>
          </div>
        </Alert>
      </div>
    );
  }

  if (overview.isLoading || !overview.data) {
    return <Skeleton className="h-96 w-full max-w-5xl" />;
  }

  const isApiError = overview.error instanceof ApiError;
  if (isApiError) {
    return (
      <div className="mx-auto max-w-2xl">
        <Alert variant="destructive">Administrator data could not be loaded.</Alert>
      </div>
    );
  }

  const data = overview.data;

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Admin</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Aggregates and failure diagnostics. Passwords, tokens, credential secrets and
          browser state are never exposed here.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Users" value={formatNumber(data.users)} hint={`${data.active_users} active`} />
        <StatCard label="Jobs stored" value={formatNumber(data.jobs)} />
        <StatCard
          label="Applications"
          value={formatNumber(data.applications)}
          hint={`${data.submitted} submitted`}
        />
        <StatCard
          label="Needs a person"
          value={formatNumber(data.open_interventions)}
          tone={data.open_interventions > 0 ? "warning" : "default"}
        />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Adapter health</CardTitle>
          <CardDescription>
            Where automation is succeeding, and where a platform has started failing.
          </CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="p-3 font-medium">Adapter</th>
                  <th className="p-3 font-medium">Runs</th>
                  <th className="p-3 font-medium">Succeeded</th>
                  <th className="p-3 font-medium">Failed</th>
                  <th className="p-3 font-medium">Paused</th>
                  <th className="p-3 font-medium">Success rate</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {data.adapters.map((adapter) => (
                  <tr key={adapter.ats}>
                    <td className="p-3 font-medium">{titleCase(adapter.ats)}</td>
                    <td className="p-3 tabular">{adapter.runs}</td>
                    <td className="p-3 tabular">{adapter.succeeded}</td>
                    <td className="p-3 tabular">{adapter.failed}</td>
                    <td className="p-3 tabular">{adapter.interventions}</td>
                    <td className="p-3 tabular">
                      {adapter.runs === 0 ? "—" : formatPercent(adapter.success_rate)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Users</CardTitle>
          <CardDescription>Disabling an account also pauses its automation.</CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="p-3 font-medium">Email</th>
                  <th className="p-3 font-medium">Plan</th>
                  <th className="p-3 font-medium">Automation</th>
                  <th className="p-3 font-medium">Applications</th>
                  <th className="p-3 font-medium">Joined</th>
                  <th className="p-3" />
                </tr>
              </thead>
              <tbody className="divide-y">
                {(users.data ?? []).map((row) => (
                  <tr key={row.id}>
                    <td className="p-3">
                      {row.email}
                      {row.role === "admin" ? (
                        <Badge variant="secondary" className="ml-2">
                          Admin
                        </Badge>
                      ) : null}
                    </td>
                    <td className="p-3">{titleCase(row.plan ?? "free")}</td>
                    <td className="p-3">
                      <Badge
                        variant={
                          !row.is_active
                            ? "destructive"
                            : row.automation_paused
                              ? "warning"
                              : row.automation_enabled
                                ? "success"
                                : "secondary"
                        }
                      >
                        {!row.is_active
                          ? "Disabled"
                          : row.automation_paused
                            ? "Paused"
                            : row.automation_enabled
                              ? "Running"
                              : "Off"}
                      </Badge>
                    </td>
                    <td className="p-3 tabular">{row.applications}</td>
                    <td className="p-3 text-muted-foreground">{formatDate(row.created_at)}</td>
                    <td className="p-3 text-right">
                      {row.is_active ? (
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => disable.mutate(row.id)}
                          disabled={disable.isPending}
                        >
                          Disable
                        </Button>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
