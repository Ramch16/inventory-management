import { BarChart3 } from "lucide-react";

import { PhasePlaceholder } from "@/components/layout/phase-placeholder";

export default function AnalyticsPage() {
  return (
    <PhasePlaceholder
      title="Analytics"
      phase="Phase 7"
      icon={BarChart3}
      summary="Trends across applications, companies, roles and match scores."
      delivers={[
        "Applications per day, by company, by role and by location",
        "Match-score distribution and response rate",
        "Automation success and failure rates over time",
      ]}
    />
  );
}
