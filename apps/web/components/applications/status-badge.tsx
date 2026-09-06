import { Badge } from "@/components/ui/badge";
import type { ApplicationStatus } from "@/lib/api/types";
import { titleCase } from "@/lib/utils";

type Variant = "default" | "secondary" | "success" | "warning" | "destructive" | "outline";

const VARIANTS: Partial<Record<ApplicationStatus, Variant>> = {
  SUBMITTED: "success",
  CONFIRMATION_CAPTURED: "success",
  INTERVIEW: "success",
  OFFER: "success",
  SUBMISSION_UNCONFIRMED: "warning",
  WAITING_FOR_VERIFICATION: "warning",
  READY_TO_SUBMIT: "warning",
  FAILED: "destructive",
  REJECTED: "destructive",
  CANCELLED: "secondary",
  WITHDRAWN: "secondary",
};

/** "Submission unconfirmed" is deliberately never shown as if it were "Applied". */
const LABELS: Partial<Record<ApplicationStatus, string>> = {
  CONFIRMATION_CAPTURED: "Applied · confirmed",
  SUBMISSION_UNCONFIRMED: "Sent · unconfirmed",
  WAITING_FOR_VERIFICATION: "Needs you",
  APPLICATION_STARTING: "Queued",
};

export function StatusBadge({ status }: { status: ApplicationStatus }) {
  return (
    <Badge variant={VARIANTS[status] ?? "secondary"}>
      {LABELS[status] ?? titleCase(status.toLowerCase())}
    </Badge>
  );
}
