"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Briefcase, Plus, Trash2 } from "lucide-react";
import { useState } from "react";

import { Field, SectionCard } from "@/components/profile/section-card";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import { ApiError } from "@/lib/api/client";
import { endpoints, queryKeys } from "@/lib/api/queries";
import type { Experience } from "@/lib/api/types";
import { formatDate } from "@/lib/utils";

const EMPTY = {
  company: "",
  title: "",
  location: "",
  start_date: "",
  end_date: "",
  is_current: false,
  accomplishments: "",
  technologies: "",
};

export function ExperienceSection({ items }: { items: Experience[] }) {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(EMPTY);

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: queryKeys.experience });
    queryClient.invalidateQueries({ queryKey: queryKeys.completeness });
    queryClient.invalidateQueries({ queryKey: queryKeys.dashboard });
  };

  const add = useMutation({
    mutationFn: () =>
      endpoints.addExperience({
        company: form.company.trim(),
        title: form.title.trim(),
        location: form.location.trim() || null,
        start_date: form.start_date || null,
        end_date: form.is_current ? null : form.end_date || null,
        is_current: form.is_current,
        accomplishments: form.accomplishments
          .split("\n")
          .map((line) => line.trim())
          .filter(Boolean),
        technologies: form.technologies
          .split(",")
          .map((item) => item.trim())
          .filter(Boolean),
        sort_order: items.length,
      }),
    onSuccess: () => {
      invalidate();
      setForm(EMPTY);
      setOpen(false);
      toast({ title: "Position added", variant: "success" });
    },
  });

  const remove = useMutation({
    mutationFn: (id: string) => endpoints.deleteExperience(id),
    onSuccess: invalidate,
  });

  const error = add.error instanceof ApiError ? add.error : null;

  return (
    <SectionCard
      title="Work experience"
      description="Tailoring may reorder and rephrase these bullets. It may never add one."
      action={
        <Button size="sm" variant={open ? "ghost" : "outline"} onClick={() => setOpen(!open)}>
          <Plus className="h-4 w-4" aria-hidden />
          {open ? "Cancel" : "Add position"}
        </Button>
      }
    >
      {open ? (
        <form
          className="mb-6 space-y-4 rounded-lg border p-4"
          onSubmit={(event) => {
            event.preventDefault();
            add.mutate();
          }}
        >
          {error ? <Alert variant="destructive">{error.message}</Alert> : null}
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Company" htmlFor="company">
              <Input
                id="company"
                required
                value={form.company}
                onChange={(event) => setForm({ ...form, company: event.target.value })}
              />
            </Field>
            <Field label="Title" htmlFor="title">
              <Input
                id="title"
                required
                value={form.title}
                onChange={(event) => setForm({ ...form, title: event.target.value })}
              />
            </Field>
            <Field label="Location" htmlFor="location">
              <Input
                id="location"
                value={form.location}
                onChange={(event) => setForm({ ...form, location: event.target.value })}
              />
            </Field>
            <Field label="Start date" htmlFor="start_date">
              <Input
                id="start_date"
                type="date"
                value={form.start_date}
                onChange={(event) => setForm({ ...form, start_date: event.target.value })}
              />
            </Field>
            <Field label="End date" htmlFor="end_date">
              <Input
                id="end_date"
                type="date"
                disabled={form.is_current}
                value={form.end_date}
                onChange={(event) => setForm({ ...form, end_date: event.target.value })}
              />
            </Field>
            <label className="flex items-end gap-2 pb-2 text-sm">
              <input
                type="checkbox"
                className="h-4 w-4 rounded border-input"
                checked={form.is_current}
                onChange={(event) =>
                  setForm({ ...form, is_current: event.target.checked, end_date: "" })
                }
              />
              I currently work here
            </label>
          </div>

          <Field
            label="Accomplishments"
            htmlFor="accomplishments"
            hint="One per line. These are the only facts a tailored resume can draw on for this role."
          >
            <Textarea
              id="accomplishments"
              rows={4}
              value={form.accomplishments}
              onChange={(event) => setForm({ ...form, accomplishments: event.target.value })}
            />
          </Field>

          <Field label="Technologies" htmlFor="technologies" hint="Comma separated.">
            <Input
              id="technologies"
              value={form.technologies}
              onChange={(event) => setForm({ ...form, technologies: event.target.value })}
            />
          </Field>

          <div className="flex justify-end">
            <Button type="submit" disabled={add.isPending}>
              {add.isPending ? "Adding…" : "Add position"}
            </Button>
          </div>
        </form>
      ) : null}

      {items.length === 0 ? (
        <EmptyState
          icon={Briefcase}
          title="No positions yet"
          description="Add at least one position, or import them from an uploaded resume. Applications cannot be tailored without grounded experience."
        />
      ) : (
        <ul className="divide-y">
          {items.map((item) => (
            <li key={item.id} className="flex items-start justify-between gap-4 py-4">
              <div className="min-w-0">
                <p className="font-medium">{item.title}</p>
                <p className="text-sm text-muted-foreground">
                  {item.company}
                  {item.location ? ` · ${item.location}` : ""}
                </p>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  {formatDate(item.start_date)} –{" "}
                  {item.is_current ? "Present" : formatDate(item.end_date)}
                </p>
                {item.accomplishments.length > 0 ? (
                  <ul className="mt-2 space-y-1 text-sm text-muted-foreground">
                    {item.accomplishments.map((bullet, index) => (
                      <li key={index}>· {bullet}</li>
                    ))}
                  </ul>
                ) : null}
                {item.technologies.length > 0 ? (
                  <p className="mt-2 text-xs text-muted-foreground">
                    {item.technologies.join(" · ")}
                  </p>
                ) : null}
              </div>
              <Button
                variant="ghost"
                size="icon"
                aria-label={`Remove ${item.title} at ${item.company}`}
                onClick={() => remove.mutate(item.id)}
                disabled={remove.isPending}
              >
                <Trash2 className="h-4 w-4" aria-hidden />
              </Button>
            </li>
          ))}
        </ul>
      )}
    </SectionCard>
  );
}
