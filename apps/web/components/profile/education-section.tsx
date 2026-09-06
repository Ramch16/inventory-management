"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { GraduationCap, Plus, Trash2 } from "lucide-react";
import { useState } from "react";

import { Field, SectionCard } from "@/components/profile/section-card";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { endpoints, queryKeys } from "@/lib/api/queries";
import type { Education } from "@/lib/api/types";
import { formatDate } from "@/lib/utils";

const EMPTY = {
  institution: "",
  degree: "",
  field_of_study: "",
  end_date: "",
  gpa: "",
};

export function EducationSection({ items }: { items: Education[] }) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(EMPTY);

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: queryKeys.education });
    queryClient.invalidateQueries({ queryKey: queryKeys.completeness });
  };

  const add = useMutation({
    mutationFn: () =>
      endpoints.addEducation({
        institution: form.institution.trim(),
        degree: form.degree.trim() || null,
        field_of_study: form.field_of_study.trim() || null,
        end_date: form.end_date || null,
        gpa: form.gpa ? Number(form.gpa) : null,
        sort_order: items.length,
      }),
    onSuccess: () => {
      invalidate();
      setForm(EMPTY);
      setOpen(false);
    },
  });

  const remove = useMutation({
    mutationFn: (id: string) => endpoints.deleteEducation(id),
    onSuccess: invalidate,
  });

  return (
    <SectionCard
      title="Education"
      action={
        <Button size="sm" variant={open ? "ghost" : "outline"} onClick={() => setOpen(!open)}>
          <Plus className="h-4 w-4" aria-hidden />
          {open ? "Cancel" : "Add"}
        </Button>
      }
    >
      {open ? (
        <form
          className="mb-6 grid gap-4 rounded-lg border p-4 sm:grid-cols-2"
          onSubmit={(event) => {
            event.preventDefault();
            add.mutate();
          }}
        >
          <Field label="Institution" htmlFor="institution">
            <Input
              id="institution"
              required
              value={form.institution}
              onChange={(event) => setForm({ ...form, institution: event.target.value })}
            />
          </Field>
          <Field label="Degree" htmlFor="degree">
            <Input
              id="degree"
              value={form.degree}
              onChange={(event) => setForm({ ...form, degree: event.target.value })}
            />
          </Field>
          <Field label="Field of study" htmlFor="field_of_study">
            <Input
              id="field_of_study"
              value={form.field_of_study}
              onChange={(event) => setForm({ ...form, field_of_study: event.target.value })}
            />
          </Field>
          <Field label="End date" htmlFor="education_end_date">
            <Input
              id="education_end_date"
              type="date"
              value={form.end_date}
              onChange={(event) => setForm({ ...form, end_date: event.target.value })}
            />
          </Field>
          <Field label="GPA" htmlFor="gpa">
            <Input
              id="gpa"
              type="number"
              step="0.01"
              min={0}
              max={5}
              value={form.gpa}
              onChange={(event) => setForm({ ...form, gpa: event.target.value })}
            />
          </Field>
          <div className="flex items-end justify-end sm:col-span-2">
            <Button type="submit" disabled={add.isPending}>
              {add.isPending ? "Adding…" : "Add education"}
            </Button>
          </div>
        </form>
      ) : null}

      {items.length === 0 ? (
        <EmptyState icon={GraduationCap} title="No education records yet" />
      ) : (
        <ul className="divide-y">
          {items.map((item) => (
            <li key={item.id} className="flex items-start justify-between gap-4 py-3">
              <div>
                <p className="font-medium">{item.institution}</p>
                <p className="text-sm text-muted-foreground">
                  {[item.degree, item.field_of_study].filter(Boolean).join(" · ") || "—"}
                </p>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  {formatDate(item.end_date)}
                  {item.gpa ? ` · GPA ${item.gpa}` : ""}
                </p>
              </div>
              <Button
                variant="ghost"
                size="icon"
                aria-label={`Remove ${item.institution}`}
                onClick={() => remove.mutate(item.id)}
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
