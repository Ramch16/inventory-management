import { TriangleAlert } from "lucide-react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Badge } from "@/components/ui/badge";
import { formatDateTime, titleCase } from "@/lib/utils";
import type { AttentionItem } from "@/lib/api/types";

export function AttentionList({ items }: { items: AttentionItem[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Needs your attention</CardTitle>
        <CardDescription>
          Runs paused for a CAPTCHA, a verification code, a legal question, or anything
          the automation would have had to guess at.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {items.length === 0 ? (
          <EmptyState
            icon={TriangleAlert}
            title="Nothing is waiting on you"
            description="When an application hits a step only you can complete, it appears here with a screenshot and a Continue button."
          />
        ) : (
          <ul className="divide-y">
            {items.map((item) => (
              <li key={item.id} className="flex items-start justify-between gap-4 py-3">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium">
                    {item.title} · {item.company}
                  </p>
                  <p className="mt-0.5 text-xs text-muted-foreground">{item.reason}</p>
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    {item.current_step ? `Step: ${item.current_step} · ` : ""}
                    {formatDateTime(item.created_at)}
                  </p>
                </div>
                <Badge variant="warning">{titleCase(item.type)}</Badge>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
