import type { LucideIcon } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface StatCardProps {
  label: string;
  value: string | number;
  hint?: string;
  icon?: LucideIcon;
  tone?: "default" | "success" | "warning" | "destructive";
}

const TONES: Record<NonNullable<StatCardProps["tone"]>, string> = {
  default: "text-foreground",
  success: "text-success",
  warning: "text-warning",
  destructive: "text-destructive",
};

export function StatCard({ label, value, hint, icon: Icon, tone = "default" }: StatCardProps) {
  return (
    <Card>
      <CardContent className="flex items-start justify-between gap-3 p-4">
        <div className="min-w-0">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            {label}
          </p>
          <p className={cn("mt-1 text-2xl font-semibold tabular", TONES[tone])}>{value}</p>
          {hint ? <p className="mt-0.5 truncate text-xs text-muted-foreground">{hint}</p> : null}
        </div>
        {Icon ? <Icon className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden /> : null}
      </CardContent>
    </Card>
  );
}
