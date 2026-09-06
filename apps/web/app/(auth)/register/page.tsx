"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError } from "@/lib/api/client";
import { endpoints, queryKeys } from "@/lib/api/queries";

const PASSWORD_RULES = "At least 10 characters, mixed case, and one digit.";

export default function RegisterPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [form, setForm] = useState({
    first_name: "",
    last_name: "",
    email: "",
    password: "",
  });

  const register = useMutation({
    mutationFn: () =>
      endpoints.register({
        email: form.email,
        password: form.password,
        first_name: form.first_name || undefined,
        last_name: form.last_name || undefined,
      }),
    onSuccess: (session) => {
      queryClient.setQueryData(queryKeys.session, session.user);
      router.replace("/dashboard");
    },
  });

  const error = register.error instanceof ApiError ? register.error : null;
  const update = (field: keyof typeof form) => (event: React.ChangeEvent<HTMLInputElement>) =>
    setForm((current) => ({ ...current, [field]: event.target.value }));

  return (
    <div>
      <h1 className="text-2xl font-semibold tracking-tight">Create your account</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Automation stays off until you complete your profile and switch it on.
      </p>

      <form
        className="mt-6 space-y-4"
        onSubmit={(event) => {
          event.preventDefault();
          register.mutate();
        }}
      >
        {error ? (
          <Alert variant="destructive" role="alert">
            <p>{error.message}</p>
            {error.fieldErrors.length > 0 ? (
              <ul className="mt-2 list-disc pl-4 text-xs">
                {error.fieldErrors.map((item) => (
                  <li key={`${item.field}-${item.message}`}>
                    <span className="font-medium">{item.field}</span>: {item.message}
                  </li>
                ))}
              </ul>
            ) : null}
          </Alert>
        ) : null}

        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1.5">
            <Label htmlFor="first_name">First name</Label>
            <Input id="first_name" autoComplete="given-name" value={form.first_name} onChange={update("first_name")} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="last_name">Last name</Label>
            <Input id="last_name" autoComplete="family-name" value={form.last_name} onChange={update("last_name")} />
          </div>
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="email">Email</Label>
          <Input
            id="email"
            type="email"
            autoComplete="email"
            required
            value={form.email}
            onChange={update("email")}
          />
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="password">Password</Label>
          <Input
            id="password"
            type="password"
            autoComplete="new-password"
            required
            minLength={10}
            value={form.password}
            onChange={update("password")}
            aria-describedby="password-rules"
          />
          <p id="password-rules" className="text-xs text-muted-foreground">
            {PASSWORD_RULES}
          </p>
        </div>

        <Button type="submit" className="w-full" disabled={register.isPending}>
          {register.isPending ? "Creating account…" : "Create account"}
        </Button>
      </form>

      <p className="mt-6 text-sm text-muted-foreground">
        Already have an account?{" "}
        <Link href="/login" className="font-medium text-foreground underline-offset-4 hover:underline">
          Sign in
        </Link>
      </p>
    </div>
  );
}
