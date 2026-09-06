import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  return new Date(value).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  return new Date(value).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

export function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return new Intl.NumberFormat().format(value);
}

export function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return `${value.toFixed(1)}%`;
}

export function formatBytes(bytes: number | null | undefined): string {
  if (!bytes) return "—";
  const units = ["B", "KB", "MB", "GB"];
  let size = bytes;
  let unit = 0;
  while (size >= 1024 && unit < units.length - 1) {
    size /= 1024;
    unit += 1;
  }
  return `${size.toFixed(unit === 0 ? 0 : 1)} ${units[unit]}`;
}

export function titleCase(value: string): string {
  return value
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}
