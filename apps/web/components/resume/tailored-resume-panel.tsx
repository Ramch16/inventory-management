"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, FileCheck2, ShieldAlert, Sparkles } from "lucide-react";
import { useState } from "react";

import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Select } from "@/components/ui/select";
import { useToast } from "@/components/ui/toast";
import { API_BASE_URL, API_PREFIX, ApiError } from "@/lib/api/client";
import { endpoints, queryKeys } from "@/lib/api/queries";
import type { ResumeTemplate, ResumeVersion } from "@/lib/api/types";
import { formatDateTime, titleCase } from "@/lib/utils";

const TEMPLATES: Array<{ value: ResumeTemplate; label: string }> = [
  { value: "ats_classic", label: "ATS Classic" },
  { value: "modern_professional", label: "Modern Professional" },
  { value: "technical", label: "Technical" },
  { value: "minimal", label: "Minimal" },
];

function ScoreRow({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-xs">
        <span>{label}</span>
        <span className="tabular text-muted-foreground">{value}</span>
      </div>
      <Progress value={value} />
    </div>
  );
}

function VersionDetail({ version }: { version: ResumeVersion }) {
  const quality = version.quality;
  const truth = version.truth_report;
  const fileUrl = (format: "pdf" | "docx") =>
    `${API_BASE_URL}${API_PREFIX}/resume-versions/${version.id}/file?fmt=${format}`;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="secondary">v{version.version}</Badge>
        <Badge variant="outline">{titleCase(version.template)}</Badge>
        {truth?.used_ai ? (
          <Badge variant="default">
            <Sparkles className="mr-1 h-3 w-3" aria-hidden />
            {version.ai_provider ?? "AI"} tailored
          </Badge>
        ) : (
          <Badge variant="secondary">Your own wording</Badge>
        )}
        <span className="text-xs text-muted-foreground">
          {formatDateTime(version.created_at)}
        </span>
      </div>

      {truth ? (
        truth.allowed ? (
          <Alert variant="success">
            <div className="flex gap-2">
              <FileCheck2 className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
              <p className="text-sm">
                Every statement in this resume traces back to a record you entered or
                approved.
              </p>
            </div>
          </Alert>
        ) : (
          <Alert variant="warning">
            <div className="flex gap-2">
              <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
              <div className="text-sm">
                <p className="font-medium">Some statements could not be verified.</p>
                <ul className="mt-1 space-y-1 text-muted-foreground">
                  {truth.reasons.slice(0, 4).map((reason) => (
                    <li key={reason}>· {reason}</li>
                  ))}
                </ul>
              </div>
            </div>
          </Alert>
        )
      ) : null}

      {truth && truth.rejected_by_generator.length > 0 ? (
        <div className="rounded-md border border-dashed p-3">
          <p className="text-xs font-medium">
            Dropped before it reached the document ({truth.rejected_by_generator.length})
          </p>
          <ul className="mt-1.5 space-y-1.5 text-xs text-muted-foreground">
            {truth.rejected_by_generator.slice(0, 5).map((item, index) => (
              <li key={index}>
                <span className="text-foreground">“{item.text}”</span>
                {item.reasons?.length ? ` — ${item.reasons[0]}` : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {quality ? (
        <div>
          <div className="mb-2 flex items-baseline gap-2">
            <span className="text-2xl font-semibold tabular">{quality.overall}</span>
            <span className="text-sm text-muted-foreground">overall quality</span>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <ScoreRow label="ATS readability" value={quality.ats_readability} />
            <ScoreRow label="Keyword coverage" value={quality.keyword_coverage} />
            <ScoreRow label="Skill coverage" value={quality.skill_coverage} />
            <ScoreRow label="Experience relevance" value={quality.experience_relevance} />
            <ScoreRow label="Formatting" value={quality.formatting_quality} />
            <ScoreRow label="Factual consistency" value={quality.factual_consistency} />
          </div>
          {quality.notes.length > 0 ? (
            <ul className="mt-3 space-y-1 text-xs text-muted-foreground">
              {quality.notes.map((note) => (
                <li key={note}>· {note}</li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}

      {version.provenance.length > 0 ? (
        <details className="rounded-md border p-3">
          <summary className="cursor-pointer text-sm font-medium">
            Where each line came from ({version.provenance.length})
          </summary>
          <ul className="mt-2 space-y-2 text-xs">
            {version.provenance.map((record, index) => (
              <li key={index}>
                <p>{record.generated_text}</p>
                <p className="mt-0.5 text-muted-foreground">
                  {record.source_ids.join(", ")} · confidence {record.confidence.toFixed(2)}
                </p>
              </li>
            ))}
          </ul>
        </details>
      ) : null}

      {version.cover_letter_text ? (
        <details className="rounded-md border p-3">
          <summary className="cursor-pointer text-sm font-medium">Cover letter</summary>
          <p className="mt-2 whitespace-pre-wrap text-sm text-muted-foreground">
            {version.cover_letter_text}
          </p>
        </details>
      ) : null}

      <div className="flex gap-2">
        <Button asChild size="sm" variant="outline">
          <a href={fileUrl("pdf")} target="_blank" rel="noreferrer">
            <Download className="h-3.5 w-3.5" aria-hidden />
            PDF
          </a>
        </Button>
        <Button asChild size="sm" variant="outline">
          <a href={fileUrl("docx")} target="_blank" rel="noreferrer">
            <Download className="h-3.5 w-3.5" aria-hidden />
            DOCX
          </a>
        </Button>
      </div>
    </div>
  );
}

export function TailoredResumePanel({ jobId }: { jobId: string }) {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [template, setTemplate] = useState<ResumeTemplate>("ats_classic");
  const [coverLetter, setCoverLetter] = useState(false);

  const versions = useQuery({
    queryKey: queryKeys.resumeVersions(jobId),
    queryFn: () => endpoints.resumeVersionsForJob(jobId),
  });

  const generate = useMutation({
    mutationFn: () =>
      endpoints.tailorResume({
        job_id: jobId,
        template,
        include_cover_letter: coverLetter,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.resumeVersions(jobId) });
      toast({ title: "Tailored resume generated", variant: "success" });
    },
    onError: (error) =>
      toast({
        title: "Could not generate",
        description: error instanceof ApiError ? error.message : "Something went wrong.",
        variant: "error",
      }),
  });

  const latest = versions.data?.[0];

  return (
    <Card>
      <CardHeader>
        <CardTitle>Tailored resume</CardTitle>
        <CardDescription>
          Built from your master resume and the records you approved. Your original file
          is never modified.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap items-end gap-3">
          <div className="w-52 space-y-1.5">
            <label htmlFor="template" className="text-sm font-medium">
              Template
            </label>
            <Select
              id="template"
              value={template}
              onChange={(event) => setTemplate(event.target.value as ResumeTemplate)}
            >
              {TEMPLATES.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </Select>
          </div>
          <label className="flex items-center gap-2 pb-2 text-sm">
            <input
              type="checkbox"
              className="h-4 w-4 rounded border-input"
              checked={coverLetter}
              onChange={(event) => setCoverLetter(event.target.checked)}
            />
            Include a cover letter
          </label>
          <Button onClick={() => generate.mutate()} disabled={generate.isPending}>
            <Sparkles className="h-4 w-4" aria-hidden />
            {generate.isPending ? "Generating…" : latest ? "Generate again" : "Generate"}
          </Button>
        </div>

        {latest ? (
          <VersionDetail version={latest} />
        ) : (
          <p className="text-sm text-muted-foreground">
            No tailored resume for this job yet.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
