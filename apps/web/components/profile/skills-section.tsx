"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Sparkles, Trash2 } from "lucide-react";
import { useState } from "react";

import { SectionCard } from "@/components/profile/section-card";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { ApiError } from "@/lib/api/client";
import { endpoints, queryKeys } from "@/lib/api/queries";
import type { Skill, SkillCategory } from "@/lib/api/types";

const CATEGORIES: Array<{ value: SkillCategory; label: string }> = [
  { value: "language", label: "Language" },
  { value: "framework", label: "Framework" },
  { value: "database", label: "Database" },
  { value: "cloud", label: "Cloud" },
  { value: "analytics", label: "Analytics" },
  { value: "devops", label: "DevOps" },
  { value: "soft", label: "Soft skill" },
  { value: "other", label: "Other" },
];

export function SkillsSection({ items }: { items: Skill[] }) {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [category, setCategory] = useState<SkillCategory>("other");
  const [years, setYears] = useState("");

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: queryKeys.skills });
    queryClient.invalidateQueries({ queryKey: queryKeys.completeness });
  };

  const add = useMutation({
    mutationFn: () =>
      endpoints.addSkill({
        name: name.trim(),
        category,
        years_experience: years ? Number(years) : null,
        is_verified: true,
      }),
    onSuccess: () => {
      invalidate();
      setName("");
      setYears("");
    },
  });

  const verify = useMutation({
    mutationFn: (skill: Skill) =>
      endpoints.updateSkill(skill.id, {
        name: skill.name,
        category: skill.category,
        years_experience: skill.years_experience,
        proficiency: skill.proficiency,
        is_verified: true,
        last_used_year: skill.last_used_year,
      }),
    onSuccess: invalidate,
  });

  const remove = useMutation({
    mutationFn: (id: string) => endpoints.deleteSkill(id),
    onSuccess: invalidate,
  });

  const error = add.error instanceof ApiError ? add.error : null;
  const unverified = items.filter((item) => !item.is_verified);

  return (
    <SectionCard
      title="Skills"
      description="A tailored resume may only mention a technology that appears here or in a position."
    >
      <form
        className="mb-5 flex flex-wrap items-end gap-3"
        onSubmit={(event) => {
          event.preventDefault();
          if (name.trim()) add.mutate();
        }}
      >
        <div className="min-w-[12rem] flex-1 space-y-1.5">
          <label htmlFor="skill-name" className="text-sm font-medium">
            Skill
          </label>
          <Input
            id="skill-name"
            value={name}
            placeholder="Python"
            onChange={(event) => setName(event.target.value)}
          />
        </div>
        <div className="w-40 space-y-1.5">
          <label htmlFor="skill-category" className="text-sm font-medium">
            Category
          </label>
          <Select
            id="skill-category"
            value={category}
            onChange={(event) => setCategory(event.target.value as SkillCategory)}
          >
            {CATEGORIES.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </Select>
        </div>
        <div className="w-28 space-y-1.5">
          <label htmlFor="skill-years" className="text-sm font-medium">
            Years
          </label>
          <Input
            id="skill-years"
            type="number"
            min={0}
            max={70}
            step="0.5"
            value={years}
            onChange={(event) => setYears(event.target.value)}
          />
        </div>
        <Button type="submit" disabled={add.isPending || !name.trim()}>
          Add
        </Button>
      </form>

      {error ? (
        <Alert variant="destructive" className="mb-4">
          {error.message}
        </Alert>
      ) : null}

      {unverified.length > 0 ? (
        <Alert variant="warning" className="mb-4">
          <p className="text-sm">
            {unverified.length} skill{unverified.length === 1 ? " was" : "s were"} imported
            from a resume and not yet confirmed. Confirm the ones you want applications to
            use.
          </p>
        </Alert>
      ) : null}

      {items.length === 0 ? (
        <EmptyState
          icon={Sparkles}
          title="No skills yet"
          description="Add the skills you want matching and tailoring to consider, or import them from a resume."
        />
      ) : (
        <ul className="flex flex-wrap gap-2">
          {items.map((item) => (
            <li
              key={item.id}
              className="flex items-center gap-2 rounded-full border py-1 pl-3 pr-1 text-sm"
            >
              <span>{item.name}</span>
              {item.years_experience ? (
                <span className="text-xs text-muted-foreground tabular">
                  {item.years_experience}y
                </span>
              ) : null}
              {item.is_verified ? null : (
                <button
                  type="button"
                  onClick={() => verify.mutate(item)}
                  className="rounded-full"
                  aria-label={`Confirm ${item.name}`}
                >
                  <Badge variant="warning">Confirm</Badge>
                </button>
              )}
              <button
                type="button"
                onClick={() => remove.mutate(item.id)}
                aria-label={`Remove ${item.name}`}
                className="rounded-full p-1 text-muted-foreground transition-colors hover:text-destructive"
              >
                <Trash2 className="h-3.5 w-3.5" aria-hidden />
              </button>
            </li>
          ))}
        </ul>
      )}
    </SectionCard>
  );
}
