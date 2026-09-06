import { cn } from "@/lib/utils";
import type { MatchRecommendation } from "@/lib/api/types";

const RING_TONE: Record<MatchRecommendation, string> = {
  APPLY: "text-success",
  REVIEW: "text-warning",
  SKIP: "text-muted-foreground",
};

export function MatchScore({
  score,
  recommendation,
  className,
}: {
  score: number;
  recommendation: MatchRecommendation;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col items-center", className)}>
      <span className={cn("text-2xl font-semibold tabular", RING_TONE[recommendation])}>
        {score}
      </span>
      <span className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
        match
      </span>
    </div>
  );
}
