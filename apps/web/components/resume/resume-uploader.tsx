"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { FileUp, Upload } from "lucide-react";
import { useRef, useState } from "react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import { ApiError } from "@/lib/api/client";
import { endpoints, queryKeys } from "@/lib/api/queries";
import { cn } from "@/lib/utils";

export function ResumeUploader({ onUploaded }: { onUploaded: (id: string) => void }) {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [pasteOpen, setPasteOpen] = useState(false);
  const [pasteTitle, setPasteTitle] = useState("");
  const [pasteContent, setPasteContent] = useState("");

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: queryKeys.resumes });
    queryClient.invalidateQueries({ queryKey: queryKeys.dashboard });
  };

  const upload = useMutation({
    mutationFn: (file: File) => endpoints.uploadResume(file),
    onSuccess: (resume) => {
      invalidate();
      onUploaded(resume.id);
      toast({
        title: "Resume uploaded",
        description: "Review what we parsed before importing it into your profile.",
        variant: "success",
      });
    },
  });

  const paste = useMutation({
    mutationFn: () => endpoints.createResumeFromText(pasteTitle || "Pasted resume", pasteContent),
    onSuccess: (resume) => {
      invalidate();
      onUploaded(resume.id);
      setPasteOpen(false);
      setPasteContent("");
      setPasteTitle("");
      toast({ title: "Resume saved", variant: "success" });
    },
  });

  const error =
    upload.error instanceof ApiError
      ? upload.error
      : paste.error instanceof ApiError
        ? paste.error
        : null;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Add a resume</CardTitle>
        <CardDescription>
          PDF, DOCX or plain text. The file you upload is stored exactly as you sent it and
          is never modified — tailored versions are always written as new documents.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {error ? <Alert variant="destructive">{error.message}</Alert> : null}

        <div
          onDragOver={(event) => {
            event.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(event) => {
            event.preventDefault();
            setDragging(false);
            const file = event.dataTransfer.files?.[0];
            if (file) upload.mutate(file);
          }}
          className={cn(
            "flex flex-col items-center justify-center rounded-lg border-2 border-dashed px-6 py-10 text-center transition-colors",
            dragging ? "border-primary bg-primary/5" : "border-border",
          )}
        >
          <FileUp className="mb-3 h-6 w-6 text-muted-foreground" aria-hidden />
          <p className="text-sm font-medium">Drop your resume here</p>
          <p className="mt-1 text-xs text-muted-foreground">or choose a file · max 10 MB</p>
          <input
            ref={inputRef}
            type="file"
            accept=".pdf,.docx,.txt,.md"
            className="hidden"
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) upload.mutate(file);
              event.target.value = "";
            }}
          />
          <div className="mt-4 flex gap-2">
            <Button
              type="button"
              size="sm"
              onClick={() => inputRef.current?.click()}
              disabled={upload.isPending}
            >
              <Upload className="h-4 w-4" aria-hidden />
              {upload.isPending ? "Uploading…" : "Choose file"}
            </Button>
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => setPasteOpen((open) => !open)}
            >
              Paste text instead
            </Button>
          </div>
        </div>

        {pasteOpen ? (
          <form
            className="space-y-3 rounded-lg border p-4"
            onSubmit={(event) => {
              event.preventDefault();
              paste.mutate();
            }}
          >
            <div className="space-y-1.5">
              <label htmlFor="paste-title" className="text-sm font-medium">
                Title
              </label>
              <Input
                id="paste-title"
                placeholder="My resume"
                value={pasteTitle}
                onChange={(event) => setPasteTitle(event.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <label htmlFor="paste-content" className="text-sm font-medium">
                Resume text
              </label>
              <Textarea
                id="paste-content"
                rows={12}
                required
                minLength={40}
                value={pasteContent}
                onChange={(event) => setPasteContent(event.target.value)}
              />
            </div>
            <div className="flex justify-end">
              <Button type="submit" disabled={paste.isPending}>
                {paste.isPending ? "Saving…" : "Save resume"}
              </Button>
            </div>
          </form>
        ) : null}
      </CardContent>
    </Card>
  );
}
