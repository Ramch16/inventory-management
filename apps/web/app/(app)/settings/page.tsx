"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { AutomationSettingsPanel } from "@/components/settings/automation-settings";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/components/ui/toast";
import { useSession } from "@/hooks/use-session";
import { ApiError } from "@/lib/api/client";
import { endpoints } from "@/lib/api/queries";
import { formatDateTime } from "@/lib/utils";

export default function SettingsPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const { data: user } = useSession();

  const [passwords, setPasswords] = useState({ current: "", next: "" });
  const [deletePassword, setDeletePassword] = useState("");
  const [confirmDelete, setConfirmDelete] = useState(false);

  const resendVerification = useMutation({
    mutationFn: endpoints.requestVerification,
    onSuccess: (result) => toast({ title: result.message, variant: "success" }),
  });

  const changePassword = useMutation({
    mutationFn: () => endpoints.changePassword(passwords.current, passwords.next),
    onSuccess: () => {
      queryClient.clear();
      toast({
        title: "Password changed",
        description: "Every other session has been signed out.",
        variant: "success",
      });
      router.replace("/login");
    },
  });

  const deleteAccount = useMutation({
    mutationFn: () => endpoints.deleteAccount(deletePassword || null),
    onSuccess: () => {
      queryClient.clear();
      router.replace("/login");
    },
  });

  const passwordError = changePassword.error instanceof ApiError ? changePassword.error : null;
  const deleteError = deleteAccount.error instanceof ApiError ? deleteAccount.error : null;

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Account, security and data controls.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Account</CardTitle>
          <CardDescription>Signed in as {user?.email}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          <div className="flex items-center justify-between gap-4">
            <span className="text-muted-foreground">E-mail verification</span>
            {user?.email_verified_at ? (
              <Badge variant="success">Verified {formatDateTime(user.email_verified_at)}</Badge>
            ) : (
              <span className="flex items-center gap-2">
                <Badge variant="warning">Not verified</Badge>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => resendVerification.mutate()}
                  disabled={resendVerification.isPending}
                >
                  Resend
                </Button>
              </span>
            )}
          </div>
          <div className="flex items-center justify-between gap-4">
            <span className="text-muted-foreground">Automation</span>
            <Badge variant={user?.automation_paused ? "warning" : "success"}>
              {user?.automation_paused ? "Paused" : "Running"}
            </Badge>
          </div>
          <div className="flex items-center justify-between gap-4">
            <span className="text-muted-foreground">Member since</span>
            <span>{formatDateTime(user?.created_at)}</span>
          </div>
        </CardContent>
      </Card>

      <AutomationSettingsPanel />

      <Card>
        <CardHeader>
          <CardTitle>Change password</CardTitle>
          <CardDescription>
            Changing your password signs out every other session immediately.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form
            className="space-y-4"
            onSubmit={(event) => {
              event.preventDefault();
              changePassword.mutate();
            }}
          >
            {passwordError ? <Alert variant="destructive">{passwordError.message}</Alert> : null}
            <div className="space-y-1.5">
              <Label htmlFor="current-password">Current password</Label>
              <Input
                id="current-password"
                type="password"
                autoComplete="current-password"
                required
                value={passwords.current}
                onChange={(event) =>
                  setPasswords((current) => ({ ...current, current: event.target.value }))
                }
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="new-password">New password</Label>
              <Input
                id="new-password"
                type="password"
                autoComplete="new-password"
                required
                minLength={10}
                value={passwords.next}
                onChange={(event) =>
                  setPasswords((current) => ({ ...current, next: event.target.value }))
                }
              />
            </div>
            <div className="flex justify-end">
              <Button type="submit" disabled={changePassword.isPending}>
                {changePassword.isPending ? "Saving…" : "Change password"}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      <Card className="border-destructive/40">
        <CardHeader>
          <CardTitle>Delete account</CardTitle>
          <CardDescription>
            Your account stops working immediately. Stored resumes and every record are
            permanently removed after a seven-day grace period.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {deleteError ? <Alert variant="destructive">{deleteError.message}</Alert> : null}
          <div className="space-y-1.5">
            <Label htmlFor="delete-password">Confirm your password</Label>
            <Input
              id="delete-password"
              type="password"
              autoComplete="current-password"
              value={deletePassword}
              onChange={(event) => setDeletePassword(event.target.value)}
            />
          </div>
          <label className="flex items-start gap-2 text-sm">
            <input
              type="checkbox"
              className="mt-0.5 h-4 w-4 rounded border-input"
              checked={confirmDelete}
              onChange={(event) => setConfirmDelete(event.target.checked)}
            />
            I understand this cannot be undone after the grace period.
          </label>
          <div className="flex justify-end">
            <Button
              variant="destructive"
              disabled={!confirmDelete || deleteAccount.isPending}
              onClick={() => deleteAccount.mutate()}
            >
              {deleteAccount.isPending ? "Deleting…" : "Delete my account"}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
