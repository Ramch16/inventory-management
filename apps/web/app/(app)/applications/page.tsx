import { Send } from "lucide-react";

import { PhasePlaceholder } from "@/components/layout/phase-placeholder";

export default function ApplicationsPage() {
  return (
    <PhasePlaceholder
      title="Applications"
      phase="Phases 4–6"
      icon={Send}
      summary="Every application, its status, and what the automation did."
      delivers={[
        "Playwright automation with per-application isolated browser contexts",
        "ATS detection and adapters for Greenhouse, Lever, Ashby, then Workday, iCIMS and SmartRecruiters",
        "Form analysis, deterministic field mapping and confidence-scored answers",
        "Submission only when no human verification is required, with confirmation capture",
        "Duplicate prevention enforced by the database, not just application code",
      ]}
    />
  );
}
