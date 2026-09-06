"use client";

import type { TooltipProps } from "recharts";

/** Tooltip in text tokens: the swatch carries identity, never the label colour. */
export function ChartTooltip({ active, payload, label }: TooltipProps<number, string>) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-md border bg-popover px-3 py-2 text-xs shadow-md">
      <p className="font-medium text-popover-foreground">{label}</p>
      <ul className="mt-1 space-y-0.5">
        {payload.map((entry) => (
          <li key={String(entry.dataKey)} className="flex items-center gap-2">
            <span
              aria-hidden
              className="h-2 w-2 shrink-0 rounded-[2px]"
              style={{ background: entry.color }}
            />
            <span className="text-muted-foreground">{entry.name}</span>
            <span className="ml-auto tabular text-popover-foreground">{entry.value}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
