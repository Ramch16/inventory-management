"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { KeyRound, ShieldCheck, Trash2 } from "lucide-react";
import { useState } from "react";

import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { useToast } from "@/components/ui/toast";
import { ApiError } from "@/lib/api/client";
import { endpoints, queryKeys } from "@/lib/api/queries";
import type { CredentialInput, CredentialKind } from "@/lib/api/types";

const KINDS: Array<{ value: CredentialKind; label: string; hint: string }> = [
  {
    value: "password",
    label: "Password",
    hint: "Used only where the site offers no other way to sign in.",
  },
  { value: "api_token", label: "API token", hint: "A token the site issued to you." },
  { value: "oauth", label: "OAuth refresh token", hint: "Preferred where the site supports it." },
  {
    value: "sso",
    label: "Single sign-on (no secret stored)",
    hint: "You complete the sign-in yourself when a run reaches it.",
  },
];

const EMPTY: CredentialInput = {
  label: "",
  kind: "password",
  host: "",
  username: "",
  secret: "",
};

function formatDate(value: string | null): string {
  if (!value) return "never";
  return new Date(value).toLocaleString();
}

export function CredentialVaultPanel() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [draft, setDraft] = useState<CredentialInput>(EMPTY);
  const [error, setError] = useState<string | null>(null);

  const credentials = useQuery({
    queryKey: queryKeys.credentials,
    queryFn: endpoints.credentials,
  });

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: queryKeys.credentials });

  const create = useMutation({
    mutationFn: (payload: CredentialInput) =>
      endpoints.createCredential({
        ...payload,
        host: payload.host?.trim() || null,
        username: payload.username?.trim() || null,
        secret: payload.secret?.trim() || null,
      }),
    onSuccess: async () => {
      setDraft(EMPTY);
      setError(null);
      await invalidate();
      toast({ title: "Credential saved", description: "It can be updated, but never read back." });
    },
    onError: (err: unknown) => {
      setError(err instanceof ApiError ? err.message : "The credential could not be saved.");
    },
  });

  const remove = useMutation({
    mutationFn: (id: string) => endpoints.deleteCredential(id),
    onSuccess: async () => {
      await invalidate();
      toast({ title: "Credential deleted" });
    },
  });

  const needsSecret = draft.kind === "password" || draft.kind === "api_token";
  const activeKind = KINDS.find((kind) => kind.value === draft.kind);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <KeyRound className="h-4 w-4" aria-hidden />
          Credential vault
        </CardTitle>
        <CardDescription>
          Sign-in details for job boards you have accounts on, so a run can continue instead of
          stopping. Secrets are encrypted before they are stored and are decrypted only by the
          automation worker at the moment it signs in — this screen cannot display one, and
          neither can support.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <Alert variant="info" className="flex items-start gap-2">
          <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          <div>
            A stored credential never lets the platform past a CAPTCHA, a one-time code or a
            multi-factor prompt. Those always pause the run and wait for you.
          </div>
        </Alert>

        <form
          className="grid gap-4 sm:grid-cols-2"
          onSubmit={(event) => {
            event.preventDefault();
            create.mutate(draft);
          }}
        >
          <div className="space-y-1.5">
            <Label htmlFor="credential-label">Name</Label>
            <Input
              id="credential-label"
              value={draft.label}
              placeholder="Workday — Acme"
              required
              onChange={(event) => setDraft({ ...draft, label: event.target.value })}
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="credential-kind">Type</Label>
            <Select
              id="credential-kind"
              value={draft.kind}
              onChange={(event) =>
                setDraft({ ...draft, kind: event.target.value as CredentialKind })
              }
            >
              {KINDS.map((kind) => (
                <option key={kind.value} value={kind.value}>
                  {kind.label}
                </option>
              ))}
            </Select>
            <p className="text-xs text-muted-foreground">{activeKind?.hint}</p>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="credential-host">Site</Label>
            <Input
              id="credential-host"
              value={draft.host ?? ""}
              placeholder="acme.wd5.myworkdayjobs.com"
              onChange={(event) => setDraft({ ...draft, host: event.target.value })}
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="credential-username">Username</Label>
            <Input
              id="credential-username"
              value={draft.username ?? ""}
              autoComplete="off"
              onChange={(event) => setDraft({ ...draft, username: event.target.value })}
            />
          </div>

          {needsSecret ? (
            <div className="space-y-1.5 sm:col-span-2">
              <Label htmlFor="credential-secret">Secret</Label>
              <Input
                id="credential-secret"
                type="password"
                value={draft.secret ?? ""}
                autoComplete="new-password"
                required
                onChange={(event) => setDraft({ ...draft, secret: event.target.value })}
              />
              <p className="text-xs text-muted-foreground">
                Encrypted with a key derived for your account. It leaves the vault only inside a
                worker, and every use is recorded below.
              </p>
            </div>
          ) : null}

          {error ? (
            <Alert variant="destructive" className="sm:col-span-2">
              {error}
            </Alert>
          ) : null}

          <div className="sm:col-span-2">
            <Button type="submit" disabled={create.isPending || !draft.label}>
              {create.isPending ? "Saving…" : "Add credential"}
            </Button>
          </div>
        </form>

        <div className="space-y-3">
          {credentials.data && credentials.data.length > 0 ? (
            credentials.data.map((credential) => (
              <div
                key={credential.id}
                className="flex items-start justify-between gap-4 rounded-lg border p-4"
              >
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium">{credential.label}</span>
                    <Badge variant="secondary">
                      {KINDS.find((kind) => kind.value === credential.kind)?.label ??
                        credential.kind}
                    </Badge>
                    {credential.has_secret ? null : (
                      <Badge variant="outline">no secret stored</Badge>
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {credential.host ?? "any site"}
                    {credential.username ? ` · ${credential.username}` : ""}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    Last used by a run: {formatDate(credential.last_used_at)}
                  </p>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  aria-label={`Delete ${credential.label}`}
                  disabled={remove.isPending}
                  onClick={() => remove.mutate(credential.id)}
                >
                  <Trash2 className="h-4 w-4" aria-hidden />
                </Button>
              </div>
            ))
          ) : (
            <EmptyState
              title="No credentials stored"
              description="Add one only for a site you already have an account on. Nothing here is required to apply through boards that let you apply as a guest."
            />
          )}
        </div>
      </CardContent>
    </Card>
  );
}
