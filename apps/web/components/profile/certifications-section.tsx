"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Award, Trash2 } from "lucide-react";
import { useState } from "react";

import { SectionCard } from "@/components/profile/section-card";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { endpoints, queryKeys } from "@/lib/api/queries";
import type { Certification } from "@/lib/api/types";
import { formatDate } from "@/lib/utils";

export function CertificationsSection({ items }: { items: Certification[] }) {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [issuer, setIssuer] = useState("");

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: queryKeys.certifications });

  const add = useMutation({
    mutationFn: () =>
      endpoints.addCertification({
        name: name.trim(),
        issuer: issuer.trim() || null,
        is_verified: true,
      }),
    onSuccess: () => {
      invalidate();
      setName("");
      setIssuer("");
    },
  });

  const remove = useMutation({
    mutationFn: (id: string) => endpoints.deleteCertification(id),
    onSuccess: invalidate,
  });

  return (
    <SectionCard
      title="Certifications"
      description="Only certifications listed here can appear on a generated resume."
    >
      <form
        className="mb-5 flex flex-wrap items-end gap-3"
        onSubmit={(event) => {
          event.preventDefault();
          if (name.trim()) add.mutate();
        }}
      >
        <div className="min-w-[14rem] flex-1 space-y-1.5">
          <label htmlFor="certification-name" className="text-sm font-medium">
            Certification
          </label>
          <Input
            id="certification-name"
            value={name}
            onChange={(event) => setName(event.target.value)}
          />
        </div>
        <div className="min-w-[10rem] flex-1 space-y-1.5">
          <label htmlFor="certification-issuer" className="text-sm font-medium">
            Issuer
          </label>
          <Input
            id="certification-issuer"
            value={issuer}
            onChange={(event) => setIssuer(event.target.value)}
          />
        </div>
        <Button type="submit" disabled={add.isPending || !name.trim()}>
          Add
        </Button>
      </form>

      {items.length === 0 ? (
        <EmptyState icon={Award} title="No certifications yet" />
      ) : (
        <ul className="divide-y">
          {items.map((item) => (
            <li key={item.id} className="flex items-center justify-between gap-4 py-3">
              <div>
                <p className="text-sm font-medium">{item.name}</p>
                <p className="text-xs text-muted-foreground">
                  {[item.issuer, formatDate(item.issued_on)].filter(Boolean).join(" · ")}
                </p>
              </div>
              <Button
                variant="ghost"
                size="icon"
                aria-label={`Remove ${item.name}`}
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
