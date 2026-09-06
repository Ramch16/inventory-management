"use client";

import { useMutation } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { endpoints } from "@/lib/api/queries";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const request = useMutation({ mutationFn: () => endpoints.forgotPassword(email) });

  return (
    <div>
      <h1 className="text-2xl font-semibold tracking-tight">Reset your password</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        We will e-mail you a link if an account exists for this address.
      </p>

      {request.isSuccess ? (
        <Alert variant="success" className="mt-6">
          {request.data?.message}
        </Alert>
      ) : (
        <form
          className="mt-6 space-y-4"
          onSubmit={(event) => {
            event.preventDefault();
            request.mutate();
          }}
        >
          <div className="space-y-1.5">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
          </div>
          <Button type="submit" className="w-full" disabled={request.isPending}>
            {request.isPending ? "Sending…" : "Send reset link"}
          </Button>
        </form>
      )}

      <p className="mt-6 text-sm text-muted-foreground">
        <Link href="/login" className="font-medium text-foreground underline-offset-4 hover:underline">
          Back to sign in
        </Link>
      </p>
    </div>
  );
}
