import type { Metadata } from "next";

import { Providers } from "@/app/providers";

import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "JobApply",
    template: "%s · JobApply",
  },
  description:
    "Find relevant jobs, verify fit, tailor each application, and submit accurately — pausing whenever a human is genuinely required.",
  robots: { index: false, follow: false },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
