import { Briefcase } from "lucide-react";

import { PhasePlaceholder } from "@/components/layout/phase-placeholder";

export default function JobsPage() {
  return (
    <PhasePlaceholder
      title="Jobs"
      phase="Phase 2"
      icon={Briefcase}
      summary="Discovered roles, scored against your profile."
      delivers={[
        "Job discovery from permitted sources and public career pages",
        "Normalization into one job shape, with duplicate detection",
        "Deterministic match scoring across skills, experience, title, education, location and authorization",
        "Job cards showing matched and missing skills, sponsorship compatibility and a recommendation",
      ]}
    />
  );
}
