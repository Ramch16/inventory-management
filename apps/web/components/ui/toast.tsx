"use client";

import { CheckCircle2, Info, TriangleAlert, X } from "lucide-react";
import * as React from "react";

import { cn } from "@/lib/utils";

type ToastVariant = "info" | "success" | "error";

interface Toast {
  id: number;
  title: string;
  description?: string;
  variant: ToastVariant;
}

interface ToastContextValue {
  toast: (input: { title: string; description?: string; variant?: ToastVariant }) => void;
}

const ToastContext = React.createContext<ToastContextValue | null>(null);

const ICONS: Record<ToastVariant, typeof Info> = {
  info: Info,
  success: CheckCircle2,
  error: TriangleAlert,
};

const STYLES: Record<ToastVariant, string> = {
  info: "border-primary/40",
  success: "border-success/50",
  error: "border-destructive/50",
};

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = React.useState<Toast[]>([]);
  const counter = React.useRef(0);

  const dismiss = React.useCallback((id: number) => {
    setToasts((current) => current.filter((item) => item.id !== id));
  }, []);

  const toast = React.useCallback<ToastContextValue["toast"]>(
    ({ title, description, variant = "info" }) => {
      counter.current += 1;
      const id = counter.current;
      setToasts((current) => [...current, { id, title, description, variant }]);
      setTimeout(() => dismiss(id), 6000);
    },
    [dismiss],
  );

  const value = React.useMemo(() => ({ toast }), [toast]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div
        aria-live="polite"
        className="pointer-events-none fixed bottom-4 right-4 z-50 flex w-full max-w-sm flex-col gap-2"
      >
        {toasts.map((item) => {
          const Icon = ICONS[item.variant];
          return (
            <div
              key={item.id}
              className={cn(
                "pointer-events-auto flex items-start gap-3 rounded-lg border bg-card p-3 shadow-lg",
                STYLES[item.variant],
              )}
            >
              <Icon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
              <div className="flex-1">
                <p className="text-sm font-medium">{item.title}</p>
                {item.description ? (
                  <p className="mt-0.5 text-xs text-muted-foreground">{item.description}</p>
                ) : null}
              </div>
              <button
                type="button"
                aria-label="Dismiss notification"
                onClick={() => dismiss(item.id)}
                className="text-muted-foreground transition-colors hover:text-foreground"
              >
                <X className="h-4 w-4" aria-hidden />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const context = React.useContext(ToastContext);
  if (!context) {
    throw new Error("useToast must be used inside a ToastProvider");
  }
  return context;
}
