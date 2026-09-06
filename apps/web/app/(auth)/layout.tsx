import { Bot } from "lucide-react";
import Link from "next/link";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <div className="flex flex-col justify-center px-6 py-12 sm:px-12">
        <div className="mx-auto w-full max-w-sm">
          <Link href="/" className="mb-8 flex items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
              <Bot className="h-4 w-4" aria-hidden />
            </span>
            <span className="text-lg font-semibold tracking-tight">JobApply</span>
          </Link>
          {children}
        </div>
      </div>

      <aside className="hidden border-l bg-muted/40 lg:flex lg:flex-col lg:justify-center lg:px-12">
        <div className="max-w-md">
          <h2 className="text-2xl font-semibold tracking-tight">
            Quality over volume.
          </h2>
          <p className="mt-3 text-sm text-muted-foreground">
            JobApply finds relevant roles, checks the fit against your verified profile,
            tailors each resume from facts you approved, and completes the repetitive
            parts of an application.
          </p>
          <dl className="mt-8 space-y-5 text-sm">
            <div>
              <dt className="font-medium">Nothing is invented</dt>
              <dd className="mt-1 text-muted-foreground">
                Every line traces back to something you entered. Unlisted technologies
                and inflated numbers are rejected before an employer ever sees them.
              </dd>
            </div>
            <div>
              <dt className="font-medium">It stops when it should</dt>
              <dd className="mt-1 text-muted-foreground">
                CAPTCHA, two-factor codes, legal attestations and anything ambiguous
                pause the run and hand control back to you.
              </dd>
            </div>
            <div>
              <dt className="font-medium">You stay in control</dt>
              <dd className="mt-1 text-muted-foreground">
                Automation stays off until you switch it on, and one button pauses
                everything.
              </dd>
            </div>
          </dl>
        </div>
      </aside>
    </div>
  );
}
