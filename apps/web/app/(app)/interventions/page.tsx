import { TriangleAlert } from "lucide-react";

import { PhasePlaceholder } from "@/components/layout/phase-placeholder";

export default function InterventionsPage() {
  return (
    <PhasePlaceholder
      title="Needs attention"
      phase="Phase 6"
      icon={TriangleAlert}
      summary="Runs paused because a person is genuinely required."
      delivers={[
        "A queue of paused runs with company, position, current step, reason and a screenshot",
        "Continue and Cancel for each one",
        "CAPTCHA and MFA handed to you in your own session — never solved or bypassed by the platform",
        "One-time code entry for OTP steps; codes are never stored",
      ]}
    />
  );
}
