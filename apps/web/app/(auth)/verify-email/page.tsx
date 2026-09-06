"use client";

import { useMutation } from "@tanstack/react-query";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef } from "react";

import { Alert } from "@/components/ui/alert";
import { ApiError } from "@/lib/api/client";
import { endpoints } from "@/lib/api/queries";

function VerifyEmail() {
  const token = useSearchParams().get("token") ?? "";
  const confirm = useMutation({ mutationFn: () => endpoints.confirmVerification(token) });
  const attempted = useRef(false);

  useEffect(() => {
    if (token && !attempted.current) {
      attempted.current = true;
      confirm.mutate();
    }
  }, [token, confirm]);

  if (!token) {
    return <Alert variant="destructive">This confirmation link is incomplete.</Alert>;
  }
  if (confirm.isPending) {
    return <p className="text-sm text-muted-foreground">Confirming your address…</p>;
  }
  if (confirm.isError) {
    const error = confirm.error instanceof ApiError ? confirm.error : null;
    return <Alert variant="destructive">{error?.message ?? "This link is not valid."}</Alert>;
  }
  return <Alert variant="success">Your e-mail address is confirmed.</Alert>;
}

export default function VerifyEmailPage() {
  return (
    <div>
      <h1 className="text-2xl font-semibold tracking-tight">Confirm your e-mail</h1>
      <div className="mt-6">
        <Suspense fallback={null}>
          <VerifyEmail />
        </Suspense>
      </div>
      <p className="mt-6 text-sm">
        <Link href="/dashboard" className="font-medium underline-offset-4 hover:underline">
          Go to your dashboard
        </Link>
      </p>
    </div>
  );
}
