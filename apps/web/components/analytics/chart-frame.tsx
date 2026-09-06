"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

interface ChartFrameProps {
  title: string;
  description?: string;
  /** Column headings for the table view. */
  columns: string[];
  /** Rows behind the chart, so the numbers are always readable as text. */
  rows: Array<Array<string | number>>;
  children: React.ReactNode;
  empty?: boolean;
  emptyMessage?: string;
}

/**
 * Every chart ships with the table behind it. That covers colour-vision and
 * contrast cases, and it means a reader can always get the exact number.
 */
export function ChartFrame({
  title,
  description,
  columns,
  rows,
  children,
  empty,
  emptyMessage = "Nothing to chart yet.",
}: ChartFrameProps) {
  const [showTable, setShowTable] = useState(false);

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <CardTitle className="text-base">{title}</CardTitle>
            {description ? <CardDescription>{description}</CardDescription> : null}
          </div>
          {!empty ? (
            <Button
              size="sm"
              variant="ghost"
              onClick={() => setShowTable((value) => !value)}
              aria-expanded={showTable}
            >
              {showTable ? "Show chart" : "Show table"}
            </Button>
          ) : null}
        </div>
      </CardHeader>
      <CardContent>
        {empty ? (
          <p className="py-8 text-center text-sm text-muted-foreground">{emptyMessage}</p>
        ) : showTable ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
                  {columns.map((column) => (
                    <th key={column} className="pb-2 font-medium">
                      {column}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y">
                {rows.map((row, index) => (
                  <tr key={index}>
                    {row.map((cell, cellIndex) => (
                      <td key={cellIndex} className={cellIndex === 0 ? "py-2" : "py-2 tabular"}>
                        {cell}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          children
        )}
      </CardContent>
    </Card>
  );
}
