"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ShieldCheck } from "lucide-react";
import { useState } from "react";

import { Field, SectionCard } from "@/components/profile/section-card";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { useToast } from "@/components/ui/toast";
import { ApiError } from "@/lib/api/client";
import { endpoints, queryKeys } from "@/lib/api/queries";
import type { WorkAuthorization } from "@/lib/api/types";

const AUTHORIZATION_TYPES = [
  { value: "citizen", label: "Citizen" },
  { value: "permanent_resident", label: "Permanent resident" },
  { value: "work_visa", label: "Work visa" },
  { value: "student_visa", label: "Student visa (with work authorization)" },
  { value: "work_permit", label: "Work permit" },
  { value: "other", label: "Other" },
];

export function WorkAuthorizationForm({ value }: { value: WorkAuthorization | null }) {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [form, setForm] = useState({
    authorization_country: value?.authorization_country ?? "",
    authorization_type: value?.authorization_type ?? "",
    authorization_expires_on: value?.authorization_expires_on ?? "",
    requires_sponsorship_now:
      value?.requires_sponsorship_now === null || value?.requires_sponsorship_now === undefined
        ? ""
        : String(value.requires_sponsorship_now),
    requires_sponsorship_future:
      value?.requires_sponsorship_future === null || value?.requires_sponsorship_future === undefined
        ? ""
        : String(value.requires_sponsorship_future),
    confirmed: false,
  });

  const save = useMutation({
    mutationFn: () =>
      endpoints.updateWorkAuthorization({
        authorization_country: form.authorization_country.trim(),
        authorization_type: form.authorization_type,
        authorization_expires_on: form.authorization_expires_on || null,
        requires_sponsorship_now: form.requires_sponsorship_now === "true",
        requires_sponsorship_future: form.requires_sponsorship_future === "true",
        confirmed: form.confirmed,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.profile });
      queryClient.invalidateQueries({ queryKey: queryKeys.completeness });
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboard });
      toast({ title: "Work authorization recorded", variant: "success" });
    },
  });

  const error = save.error instanceof ApiError ? save.error : null;
  const complete =
    form.authorization_country.trim() !== "" &&
    form.authorization_type !== "" &&
    form.requires_sponsorship_now !== "" &&
    form.requires_sponsorship_future !== "";

  return (
    <SectionCard
      title="Work authorization"
      description="These answers go onto applications exactly as you give them."
      action={
        value?.declared ? (
          <Badge variant="success">Declared</Badge>
        ) : (
          <Badge variant="warning">Not declared</Badge>
        )
      }
    >
      <Alert variant="info" className="mb-4">
        <div className="flex gap-3">
          <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          <div className="text-sm">
            <p className="font-medium">This is never inferred and never generated.</p>
            <p className="mt-1 text-muted-foreground">
              The platform will not read work authorization out of your resume and will not
              let a model answer these questions. Until every field below is answered and
              confirmed, automated submission stays blocked.
            </p>
          </div>
        </div>
      </Alert>

      <form
        className="space-y-4"
        onSubmit={(event) => {
          event.preventDefault();
          save.mutate();
        }}
      >
        {error ? <Alert variant="destructive">{error.message}</Alert> : null}

        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Country of authorization" htmlFor="authorization_country">
            <Input
              id="authorization_country"
              required
              value={form.authorization_country}
              onChange={(event) =>
                setForm((current) => ({ ...current, authorization_country: event.target.value }))
              }
            />
          </Field>

          <Field label="Authorization type" htmlFor="authorization_type">
            <Select
              id="authorization_type"
              required
              value={form.authorization_type}
              onChange={(event) =>
                setForm((current) => ({ ...current, authorization_type: event.target.value }))
              }
            >
              <option value="">Select…</option>
              {AUTHORIZATION_TYPES.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </Select>
          </Field>

          <Field
            label="Expires on"
            htmlFor="authorization_expires_on"
            hint="Leave blank if it does not expire."
          >
            <Input
              id="authorization_expires_on"
              type="date"
              value={form.authorization_expires_on}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  authorization_expires_on: event.target.value,
                }))
              }
            />
          </Field>

          <Field label="Do you need sponsorship now?" htmlFor="requires_sponsorship_now">
            <Select
              id="requires_sponsorship_now"
              required
              value={form.requires_sponsorship_now}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  requires_sponsorship_now: event.target.value,
                }))
              }
            >
              <option value="">Select…</option>
              <option value="false">No</option>
              <option value="true">Yes</option>
            </Select>
          </Field>

          <Field
            label="Will you need sponsorship in the future?"
            htmlFor="requires_sponsorship_future"
          >
            <Select
              id="requires_sponsorship_future"
              required
              value={form.requires_sponsorship_future}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  requires_sponsorship_future: event.target.value,
                }))
              }
            >
              <option value="">Select…</option>
              <option value="false">No</option>
              <option value="true">Yes</option>
            </Select>
          </Field>
        </div>

        <label className="flex items-start gap-2.5 rounded-md border p-3 text-sm">
          <input
            type="checkbox"
            className="mt-0.5 h-4 w-4 rounded border-input"
            checked={form.confirmed}
            onChange={(event) =>
              setForm((current) => ({ ...current, confirmed: event.target.checked }))
            }
          />
          <span>
            I confirm these answers are accurate and may be submitted to employers on my
            behalf.
          </span>
        </label>

        <div className="flex justify-end">
          <Button type="submit" disabled={!complete || !form.confirmed || save.isPending}>
            {save.isPending ? "Saving…" : "Save work authorization"}
          </Button>
        </div>
      </form>
    </SectionCard>
  );
}
