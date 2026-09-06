"use client";

import { useMutation } from "@tanstack/react-query";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError } from "@/lib/api/client";
import { endpoints } from "@/lib/api/queries";

function ResetPasswordForm() {
  const token = useSearchParams().get("token") ?? "";
  const [password, setPassword] = useState("");

  const reset = useMutation({ mutationFn: () => endpoints.resetPassword(token, password) });
  const error = reset.error instanceof ApiError ? reset.error : null;

  if (!token) {
    return (
      <Alert variant="destructive">
        This reset link is incomplete. Request a new one from the sign-in page.
      </Alert>
    );
  }

  if (reset.isSuccess) {
    return (
      <div>
        <Alert variant="success">Your password has been changed.</Alert>
        <p className="mt-6 text-sm">
          <Link href="/login" className="font-medium underline-offset-4 hover:underline">
            Sign in with your new password
          </Link>
        </p>
      </div>
    );
  }

  return (
    <form
      className="space-y-4"
      onSubmit={(event) => {
        event.preventDefault();
        reset.mutate();
      }}
    >
      {error ? <Alert variant="destructive">{error.message}</Alert> : null}
      <div className="space-y-1.5">
        <Label htmlFor="password">New password</Label>
        <Input
          id="password"
          type="password"
          autoComplete="new-password"
          required
          minLength={10}
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />
        <p className="text-xs text-muted-foreground">
          At least 10 characters, mixed case, and one digit.
        </p>
      </div>
      <Button type="submit" className="w-full" disabled={reset.isPending}>
        {reset.isPending ? "Saving…" : "Set new password"}
      </Button>
    </form>
  );
}

export default function ResetPasswordPage() {
  return (
    <div>
      <h1 className="text-2xl font-semibold tracking-tight">Choose a new password</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Setting a new password signs out every other session.
      </p>
      <div className="mt-6">
        <Suspense fallback={null}>
          <ResetPasswordForm />
        </Suspense>
      </div>
    </div>
  );
}
