"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileText, Star, Trash2 } from "lucide-react";
import { useState } from "react";

import { ParsedPreview } from "@/components/resume/parsed-preview";
import { ResumeUploader } from "@/components/resume/resume-uploader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { API_BASE_URL, API_PREFIX } from "@/lib/api/client";
import { endpoints, queryKeys } from "@/lib/api/queries";
import { formatDate } from "@/lib/utils";

export default function ResumePage() {
  const queryClient = useQueryClient();
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const resumes = useQuery({ queryKey: queryKeys.resumes, queryFn: endpoints.resumes });
  const activeId = selectedId ?? resumes.data?.[0]?.id ?? null;
  const selected = useQuery({
    queryKey: activeId ? queryKeys.resume(activeId) : ["resumes", "none"],
    queryFn: () => endpoints.resume(activeId as string),
    enabled: Boolean(activeId),
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: queryKeys.resumes });
    queryClient.invalidateQueries({ queryKey: queryKeys.dashboard });
  };

  const setMaster = useMutation({
    mutationFn: (id: string) => endpoints.setMasterResume(id),
    onSuccess: invalidate,
  });

  const remove = useMutation({
    mutationFn: (id: string) => endpoints.deleteResume(id),
    onSuccess: (_, id) => {
      if (activeId === id) setSelectedId(null);
      invalidate();
    },
  });

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Resumes</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Your master resume is the source of truth. Tailored versions for individual jobs
          are generated from it and stored separately.
        </p>
      </div>

      <ResumeUploader onUploaded={(id) => setSelectedId(id)} />

      <Card>
        <CardHeader>
          <CardTitle>Your resumes</CardTitle>
          <CardDescription>The master resume is used for tailoring.</CardDescription>
        </CardHeader>
        <CardContent>
          {resumes.isLoading ? (
            <Skeleton className="h-24 w-full" />
          ) : (resumes.data ?? []).length === 0 ? (
            <EmptyState
              icon={FileText}
              title="No resumes yet"
              description="Upload a PDF or DOCX, or paste your resume text above."
            />
          ) : (
            <ul className="divide-y">
              {(resumes.data ?? []).map((resume) => (
                <li key={resume.id} className="flex items-center justify-between gap-4 py-3">
                  <button
                    type="button"
                    onClick={() => setSelectedId(resume.id)}
                    className="min-w-0 flex-1 text-left"
                  >
                    <span className="flex items-center gap-2">
                      <span className="truncate text-sm font-medium">{resume.title}</span>
                      {resume.is_master ? <Badge variant="success">Master</Badge> : null}
                      {resume.parse_status !== "parsed" ? (
                        <Badge variant="warning">{resume.parse_status}</Badge>
                      ) : null}
                    </span>
                    <span className="mt-0.5 block text-xs text-muted-foreground">
                      {resume.original_filename ?? "Pasted text"} · added{" "}
                      {formatDate(resume.created_at)}
                    </span>
                  </button>

                  <div className="flex shrink-0 items-center gap-1">
                    {resume.original_filename ? (
                      <Button asChild variant="ghost" size="sm">
                        <a
                          href={`${API_BASE_URL}${API_PREFIX}/resumes/${resume.id}/file`}
                          target="_blank"
                          rel="noreferrer"
                        >
                          Download
                        </a>
                      </Button>
                    ) : null}
                    {resume.is_master ? null : (
                      <Button
                        variant="ghost"
                        size="icon"
                        aria-label={`Make ${resume.title} the master resume`}
                        onClick={() => setMaster.mutate(resume.id)}
                      >
                        <Star className="h-4 w-4" aria-hidden />
                      </Button>
                    )}
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label={`Delete ${resume.title}`}
                      onClick={() => remove.mutate(resume.id)}
                    >
                      <Trash2 className="h-4 w-4" aria-hidden />
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      {selected.data ? <ParsedPreview resume={selected.data} /> : null}
    </div>
  );
}
