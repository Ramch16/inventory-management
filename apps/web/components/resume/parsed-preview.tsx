"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { TriangleAlert } from "lucide-react";

import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useToast } from "@/components/ui/toast";
import { endpoints, queryKeys } from "@/lib/api/queries";
import type { Resume } from "@/lib/api/types";
import { formatDate } from "@/lib/utils";

export function ParsedPreview({ resume }: { resume: Resume }) {
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const importIntoProfile = useMutation({
    mutationFn: () => endpoints.importResume(resume.id),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.profile });
      queryClient.invalidateQueries({ queryKey: queryKeys.experience });
      queryClient.invalidateQueries({ queryKey: queryKeys.education });
      queryClient.invalidateQueries({ queryKey: queryKeys.skills });
      queryClient.invalidateQueries({ queryKey: queryKeys.certifications });
      queryClient.invalidateQueries({ queryKey: queryKeys.completeness });
      toast({
        title: "Imported into your profile",
        description: `${result.experience_added} positions, ${result.skills_added} skills, ${result.education_added} education records.`,
        variant: "success",
      });
    },
  });

  const parsed = resume.structured;

  if (resume.parse_status === "failed" || !parsed) {
    return (
      <Alert variant="destructive">
        <p className="font-medium">This resume could not be parsed.</p>
        <p className="mt-1 text-sm text-muted-foreground">
          {resume.parse_error ?? "Try uploading a text-based PDF, or paste the text instead."}
        </p>
      </Alert>
    );
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <CardTitle>What we read</CardTitle>
            <CardDescription>
              These are suggestions. Nothing becomes part of your profile until you import
              it, and work authorization is never taken from a resume.
            </CardDescription>
          </div>
          <Button
            size="sm"
            onClick={() => importIntoProfile.mutate()}
            disabled={importIntoProfile.isPending}
          >
            {importIntoProfile.isPending ? "Importing…" : "Import into profile"}
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-5">
        {parsed.warnings.length > 0 ? (
          <Alert variant="warning">
            <div className="flex gap-2">
              <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
              <ul className="space-y-1 text-sm">
                {parsed.warnings.map((warning) => (
                  <li key={warning}>{warning}</li>
                ))}
              </ul>
            </div>
          </Alert>
        ) : null}

        <section>
          <h3 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Contact
          </h3>
          <dl className="mt-2 grid gap-x-6 gap-y-1 text-sm sm:grid-cols-2">
            {[
              ["Name", parsed.contact.full_name],
              ["Email", parsed.contact.email],
              ["Phone", parsed.contact.phone],
              ["Location", parsed.contact.location],
              ["LinkedIn", parsed.contact.linkedin_url],
              ["GitHub", parsed.contact.github_url],
            ].map(([label, value]) => (
              <div key={label} className="flex gap-2">
                <dt className="w-20 shrink-0 text-muted-foreground">{label}</dt>
                <dd className="truncate">{value || "—"}</dd>
              </div>
            ))}
          </dl>
        </section>

        {parsed.positions.length > 0 ? (
          <section>
            <h3 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Experience
            </h3>
            <ul className="mt-2 space-y-3">
              {parsed.positions.map((position, index) => (
                <li key={index} className="rounded-md border p-3">
                  <p className="text-sm font-medium">
                    {position.title ?? "Unknown title"} · {position.company ?? "Unknown company"}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {formatDate(position.start_date)} –{" "}
                    {position.is_current ? "Present" : formatDate(position.end_date)}
                    {position.location ? ` · ${position.location}` : ""}
                  </p>
                  {position.bullets.length > 0 ? (
                    <ul className="mt-2 space-y-1 text-sm text-muted-foreground">
                      {position.bullets.map((bullet, bulletIndex) => (
                        <li key={bulletIndex}>· {bullet}</li>
                      ))}
                    </ul>
                  ) : null}
                </li>
              ))}
            </ul>
          </section>
        ) : null}

        {parsed.skills.length > 0 ? (
          <section>
            <h3 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Skills
            </h3>
            <ul className="mt-2 flex flex-wrap gap-1.5">
              {parsed.skills.map((skill) => (
                <li key={skill}>
                  <Badge variant="secondary">{skill}</Badge>
                </li>
              ))}
            </ul>
          </section>
        ) : null}

        {parsed.education.length > 0 ? (
          <section>
            <h3 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Education
            </h3>
            <ul className="mt-2 space-y-1 text-sm">
              {parsed.education.map((record, index) => (
                <li key={index}>
                  {record.institution}
                  {record.degree ? ` — ${record.degree}` : ""}
                  {record.gpa ? ` · GPA ${record.gpa}` : ""}
                </li>
              ))}
            </ul>
          </section>
        ) : null}
      </CardContent>
    </Card>
  );
}
