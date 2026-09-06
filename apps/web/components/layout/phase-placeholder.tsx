import type { LucideIcon } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

interface PhasePlaceholderProps {
  title: string;
  phase: string;
  icon: LucideIcon;
  summary: string;
  delivers: string[];
}

/**
 * Shown for routes whose feature ships in a later phase. It states plainly what is
 * not built yet rather than rendering invented jobs or applications.
 */
export function PhasePlaceholder({
  title,
  phase,
  icon: Icon,
  summary,
  delivers,
}: PhasePlaceholderProps) {
  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        <p className="mt-1 text-sm text-muted-foreground">{summary}</p>
      </div>

      <Card>
        <CardHeader>
          <div className="mb-1 flex items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-muted">
              <Icon className="h-4 w-4 text-muted-foreground" aria-hidden />
            </span>
            <CardTitle>Not built yet — {phase}</CardTitle>
          </div>
          <CardDescription>
            This screen has no data to show because the feature behind it has not shipped.
            It will not display placeholder jobs or invented applications.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <p className="text-sm font-medium">What this phase delivers</p>
            <ul className="mt-2 space-y-1 text-sm text-muted-foreground">
              {delivers.map((item) => (
                <li key={item}>· {item}</li>
              ))}
            </ul>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="outline">
              <Link href="/profile">Complete your profile</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/resume">Upload a resume</Link>
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
