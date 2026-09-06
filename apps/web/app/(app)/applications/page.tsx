"use client";

import { useQuery } from "@tanstack/react-query";
import { Send } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { StatusBadge } from "@/components/applications/status-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { API_BASE_URL, API_PREFIX } from "@/lib/api/client";
import { endpoints, queryKeys } from "@/lib/api/queries";
import { formatDate } from "@/lib/utils";

const STATUSES = [
  "", "APPROVED", "APPLICATION_STARTING", "WAITING_FOR_VERIFICATION", "READY_TO_SUBMIT",
  "SUBMITTED", "CONFIRMATION_CAPTURED", "SUBMISSION_UNCONFIRMED", "FAILED", "INTERVIEW",
  "REJECTED", "OFFER", "CANCELLED",
];

export default function ApplicationsPage() {
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const params = { page, page_size: 25, status: status || undefined };

  const applications = useQuery({
    queryKey: queryKeys.applications(params),
    queryFn: () => endpoints.applications(params),
    refetchInterval: 30_000,
  });

  const total = applications.data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / 25));

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Applications</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Every application and exactly where it stands.
          </p>
        </div>
        <Button asChild variant="outline">
          <a href={`${API_BASE_URL}${API_PREFIX}/applications/export`}>Export CSV</a>
        </Button>
      </div>

      <Card>
        <CardContent className="flex flex-wrap items-end gap-3 p-4">
          <div className="w-64 space-y-1.5">
            <label htmlFor="status-filter" className="text-sm font-medium">
              Status
            </label>
            <Select
              id="status-filter"
              value={status}
              onChange={(event) => {
                setPage(1);
                setStatus(event.target.value);
              }}
            >
              {STATUSES.map((value) => (
                <option key={value || "any"} value={value}>
                  {value || "Any status"}
                </option>
              ))}
            </Select>
          </div>
        </CardContent>
      </Card>

      {applications.isLoading ? (
        <Skeleton className="h-64 w-full" />
      ) : total === 0 ? (
        <EmptyState
          icon={Send}
          title="No applications yet"
          description="Approve a job you like, generate its tailored resume, and start the application from the job page."
          action={
            <Button asChild>
              <Link href="/jobs">Browse jobs</Link>
            </Button>
          }
        />
      ) : (
        <Card>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
                    <th className="p-3 font-medium">Role</th>
                    <th className="p-3 font-medium">Company</th>
                    <th className="p-3 font-medium">Match</th>
                    <th className="p-3 font-medium">Status</th>
                    <th className="p-3 font-medium">Submitted</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {applications.data?.items.map((application) => (
                    <tr key={application.id} className="hover:bg-muted/40">
                      <td className="max-w-[18rem] p-3">
                        <Link
                          href={`/applications/${application.id}`}
                          className="truncate font-medium underline-offset-4 hover:underline"
                        >
                          {application.title}
                        </Link>
                        {application.open_interventions > 0 ? (
                          <Badge variant="warning" className="ml-2">
                            Needs you
                          </Badge>
                        ) : null}
                      </td>
                      <td className="p-3 text-muted-foreground">{application.company_name}</td>
                      <td className="p-3 tabular">
                        {application.match_score === null ? "—" : `${application.match_score}%`}
                      </td>
                      <td className="p-3">
                        <StatusBadge status={application.status} />
                      </td>
                      <td className="p-3 text-muted-foreground">
                        {formatDate(application.submitted_at)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {totalPages > 1 ? (
        <div className="flex items-center justify-between text-sm">
          <span className="text-muted-foreground">
            Page {page} of {totalPages} · {total} applications
          </span>
          <div className="flex gap-2">
            <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => setPage(page - 1)}>
              Previous
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={page >= totalPages}
              onClick={() => setPage(page + 1)}
            >
              Next
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
