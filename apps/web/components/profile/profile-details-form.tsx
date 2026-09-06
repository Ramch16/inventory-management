"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { Field, SectionCard } from "@/components/profile/section-card";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import { ApiError } from "@/lib/api/client";
import { endpoints, queryKeys } from "@/lib/api/queries";
import type { Profile } from "@/lib/api/types";

type FormState = Record<string, string>;

function toFormState(profile: Profile): FormState {
  const value = (input: string | number | null | undefined) =>
    input === null || input === undefined ? "" : String(input);
  return {
    first_name: value(profile.first_name),
    last_name: value(profile.last_name),
    preferred_name: value(profile.preferred_name),
    email: value(profile.email),
    phone: value(profile.phone),
    city: value(profile.city),
    state: value(profile.state),
    country: value(profile.country),
    postal_code: value(profile.postal_code),
    linkedin_url: value(profile.linkedin_url),
    github_url: value(profile.github_url),
    portfolio_url: value(profile.portfolio_url),
    current_title: value(profile.current_title),
    years_experience: value(profile.years_experience),
    summary: value(profile.summary),
    desired_titles: (profile.desired_titles ?? []).join(", "),
    desired_locations: (profile.desired_locations ?? []).join(", "),
    desired_industries: (profile.desired_industries ?? []).join(", "),
    remote_preference: value(profile.remote_preference),
    salary_min: value(profile.salary_min),
    salary_max: value(profile.salary_max),
    open_to_relocation: profile.open_to_relocation === null ? "" : String(profile.open_to_relocation),
  };
}

function toPayload(form: FormState): Record<string, unknown> {
  const text = (key: string) => (form[key]?.trim() ? form[key]!.trim() : null);
  const list = (key: string) =>
    (form[key] ?? "")
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
  const number = (key: string) => (form[key]?.trim() ? Number(form[key]) : null);

  return {
    first_name: text("first_name"),
    last_name: text("last_name"),
    preferred_name: text("preferred_name"),
    email: text("email"),
    phone: text("phone"),
    city: text("city"),
    state: text("state"),
    country: text("country"),
    postal_code: text("postal_code"),
    linkedin_url: text("linkedin_url"),
    github_url: text("github_url"),
    portfolio_url: text("portfolio_url"),
    current_title: text("current_title"),
    years_experience: number("years_experience"),
    summary: text("summary"),
    desired_titles: list("desired_titles"),
    desired_locations: list("desired_locations"),
    desired_industries: list("desired_industries"),
    remote_preference: text("remote_preference"),
    salary_min: number("salary_min"),
    salary_max: number("salary_max"),
    open_to_relocation: form.open_to_relocation === "" ? null : form.open_to_relocation === "true",
  };
}

export function ProfileDetailsForm({ profile }: { profile: Profile }) {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [form, setForm] = useState<FormState>(() => toFormState(profile));

  useEffect(() => setForm(toFormState(profile)), [profile]);

  const save = useMutation({
    mutationFn: () => endpoints.updateProfile(toPayload(form) as Partial<Profile>),
    onSuccess: (updated) => {
      queryClient.setQueryData(queryKeys.profile, updated);
      queryClient.invalidateQueries({ queryKey: queryKeys.completeness });
      toast({ title: "Profile saved", variant: "success" });
    },
  });

  const error = save.error instanceof ApiError ? save.error : null;
  const update = (key: string) => (event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
    setForm((current) => ({ ...current, [key]: event.target.value }));

  return (
    <form
      className="space-y-6"
      onSubmit={(event) => {
        event.preventDefault();
        save.mutate();
      }}
    >
      {error ? (
        <Alert variant="destructive">
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

      <SectionCard title="Personal" description="Used to fill the identity fields of an application.">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="First name" htmlFor="first_name">
            <Input id="first_name" value={form.first_name} onChange={update("first_name")} />
          </Field>
          <Field label="Last name" htmlFor="last_name">
            <Input id="last_name" value={form.last_name} onChange={update("last_name")} />
          </Field>
          <Field label="Preferred name" htmlFor="preferred_name">
            <Input id="preferred_name" value={form.preferred_name} onChange={update("preferred_name")} />
          </Field>
          <Field label="Contact e-mail" htmlFor="email">
            <Input id="email" type="email" value={form.email} onChange={update("email")} />
          </Field>
          <Field label="Phone" htmlFor="phone">
            <Input id="phone" value={form.phone} onChange={update("phone")} />
          </Field>
          <Field label="City" htmlFor="city">
            <Input id="city" value={form.city} onChange={update("city")} />
          </Field>
          <Field label="State / region" htmlFor="state">
            <Input id="state" value={form.state} onChange={update("state")} />
          </Field>
          <Field label="Country" htmlFor="country">
            <Input id="country" value={form.country} onChange={update("country")} />
          </Field>
          <Field label="Postal code" htmlFor="postal_code">
            <Input id="postal_code" value={form.postal_code} onChange={update("postal_code")} />
          </Field>
        </div>

        <div className="mt-4 grid gap-4 sm:grid-cols-3">
          <Field label="LinkedIn" htmlFor="linkedin_url">
            <Input id="linkedin_url" value={form.linkedin_url} onChange={update("linkedin_url")} />
          </Field>
          <Field label="GitHub" htmlFor="github_url">
            <Input id="github_url" value={form.github_url} onChange={update("github_url")} />
          </Field>
          <Field label="Portfolio" htmlFor="portfolio_url">
            <Input id="portfolio_url" value={form.portfolio_url} onChange={update("portfolio_url")} />
          </Field>
        </div>
      </SectionCard>

      <SectionCard
        title="Professional"
        description="What you do today and what you are looking for. Matching uses these."
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Current title" htmlFor="current_title">
            <Input id="current_title" value={form.current_title} onChange={update("current_title")} />
          </Field>
          <Field label="Years of experience" htmlFor="years_experience">
            <Input
              id="years_experience"
              type="number"
              min={0}
              max={70}
              step="0.5"
              value={form.years_experience}
              onChange={update("years_experience")}
            />
          </Field>
        </div>

        <div className="mt-4">
          <Field
            label="Summary"
            htmlFor="summary"
            hint="Tailoring may rephrase this, but it will never add a claim that is not in your records."
          >
            <Textarea id="summary" rows={4} value={form.summary} onChange={update("summary")} />
          </Field>
        </div>

        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <Field label="Desired titles" htmlFor="desired_titles" hint="Comma separated.">
            <Input id="desired_titles" value={form.desired_titles} onChange={update("desired_titles")} />
          </Field>
          <Field label="Desired locations" htmlFor="desired_locations" hint="Comma separated.">
            <Input id="desired_locations" value={form.desired_locations} onChange={update("desired_locations")} />
          </Field>
          <Field label="Desired industries" htmlFor="desired_industries" hint="Comma separated.">
            <Input id="desired_industries" value={form.desired_industries} onChange={update("desired_industries")} />
          </Field>
          <Field label="Work setting" htmlFor="remote_preference">
            <Select id="remote_preference" value={form.remote_preference} onChange={update("remote_preference")}>
              <option value="">No preference</option>
              <option value="remote">Remote</option>
              <option value="hybrid">Hybrid</option>
              <option value="onsite">On-site</option>
            </Select>
          </Field>
          <Field label="Minimum salary" htmlFor="salary_min">
            <Input id="salary_min" type="number" min={0} value={form.salary_min} onChange={update("salary_min")} />
          </Field>
          <Field label="Maximum salary" htmlFor="salary_max">
            <Input id="salary_max" type="number" min={0} value={form.salary_max} onChange={update("salary_max")} />
          </Field>
          <Field label="Open to relocation" htmlFor="open_to_relocation">
            <Select id="open_to_relocation" value={form.open_to_relocation} onChange={update("open_to_relocation")}>
              <option value="">Not specified</option>
              <option value="true">Yes</option>
              <option value="false">No</option>
            </Select>
          </Field>
        </div>
      </SectionCard>

      <div className="flex justify-end">
        <Button type="submit" disabled={save.isPending}>
          {save.isPending ? "Saving…" : "Save profile"}
        </Button>
      </div>
    </form>
  );
}
