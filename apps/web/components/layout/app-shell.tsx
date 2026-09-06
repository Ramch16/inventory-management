"use client";

import { useQuery } from "@tanstack/react-query";
import { Bot, LogOut, Menu, X } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Nav } from "@/components/layout/nav";
import { ThemeToggle } from "@/components/layout/theme-toggle";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useLogout, useSession } from "@/hooks/use-session";
import { endpoints, queryKeys } from "@/lib/api/queries";

export function AppShell({ children }: { children: React.ReactNode }) {
  const { data: user } = useSession();
  const logout = useLogout();
  const [mobileOpen, setMobileOpen] = useState(false);

  const unread = useQuery({
    queryKey: queryKeys.unreadCount,
    queryFn: endpoints.unreadCount,
    refetchInterval: 60_000,
  });

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[16rem_1fr]">
      <aside className="hidden border-r bg-card/40 lg:flex lg:flex-col">
        <div className="flex h-14 items-center gap-2 border-b px-5">
          <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <Bot className="h-4 w-4" aria-hidden />
          </span>
          <span className="font-semibold tracking-tight">JobApply</span>
        </div>
        <div className="flex-1 overflow-y-auto p-3">
          <Nav />
        </div>
        <div className="border-t p-3">
          {user ? (
            <div className="mb-2 px-3 py-1">
              <p className="truncate text-sm font-medium">{user.email}</p>
              <p className="text-xs text-muted-foreground">
                {user.automation_paused ? "Automation paused" : "Automation running"}
              </p>
            </div>
          ) : null}
          <Button
            variant="ghost"
            className="w-full justify-start text-muted-foreground"
            onClick={() => logout.mutate()}
            disabled={logout.isPending}
          >
            <LogOut className="h-4 w-4" aria-hidden />
            Sign out
          </Button>
        </div>
      </aside>

      <div className="flex min-h-screen flex-col">
        <header className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b bg-background/95 px-4 backdrop-blur sm:px-6">
          <Button
            variant="ghost"
            size="icon"
            className="lg:hidden"
            aria-label={mobileOpen ? "Close menu" : "Open menu"}
            onClick={() => setMobileOpen((open) => !open)}
          >
            {mobileOpen ? <X className="h-4 w-4" aria-hidden /> : <Menu className="h-4 w-4" aria-hidden />}
          </Button>

          <div className="flex-1" />

          {unread.data && unread.data.count > 0 ? (
            <Badge variant="default">{unread.data.count} unread</Badge>
          ) : null}
          {user && !user.email_verified_at ? (
            <Link href="/settings">
              <Badge variant="warning">Confirm your e-mail</Badge>
            </Link>
          ) : null}
          <ThemeToggle />
        </header>

        {mobileOpen ? (
          <div className="border-b bg-card p-3 lg:hidden">
            <Nav onNavigate={() => setMobileOpen(false)} />
          </div>
        ) : null}

        <main className="flex-1 px-4 py-6 sm:px-6 lg:px-8">{children}</main>
      </div>
    </div>
  );
}
