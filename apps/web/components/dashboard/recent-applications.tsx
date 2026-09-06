import { Send } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { formatDate, titleCase } from "@/lib/utils";
import type { RecentApplication } from "@/lib/api/types";

const TONE_BY_STATUS: Record<string, "default" | "success" | "warning" | "destructive" | "secondary"> = {
  SUBMITTED: "success",
  CONFIRMATION_CAPTURED: "success",
  OFFER: "success",
  INTERVIEW: "success",
  SUBMISSION_UNCONFIRMED: "warning",
  WAITING_FOR_VERIFICATION: "warning",
  FAILED: "destructive",
  REJECTED: "destructive",
};

export function RecentApplications({ items }: { items: RecentApplication[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Recent applications</CardTitle>
        <CardDescription>The last few applications and where each one stands.</CardDescription>
      </CardHeader>
      <CardContent>
        {items.length === 0 ? (
          <EmptyState
            icon={Send}
            title="No applications yet"
            description="Once job discovery and matching are switched on, approved matches appear here as they progress."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="pb-2 font-medium">Role</th>
                  <th className="pb-2 font-medium">Company</th>
                  <th className="pb-2 font-medium">Match</th>
                  <th className="pb-2 font-medium">Status</th>
                  <th className="pb-2 font-medium">Submitted</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {items.map((item) => (
                  <tr key={item.id}>
                    <td className="max-w-[16rem] truncate py-2.5 font-medium">{item.title}</td>
                    <td className="py-2.5 text-muted-foreground">{item.company}</td>
                    <td className="py-2.5 tabular">
                      {item.match_score === null ? "—" : `${item.match_score}%`}
                    </td>
                    <td className="py-2.5">
                      <Badge variant={TONE_BY_STATUS[item.status] ?? "secondary"}>
                        {titleCase(item.status.toLowerCase())}
                      </Badge>
                    </td>
                    <td className="py-2.5 text-muted-foreground">{formatDate(item.submitted_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
