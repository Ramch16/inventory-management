"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { ChartFrame } from "@/components/analytics/chart-frame";
import { ChartTooltip } from "@/components/analytics/tooltip";
import { StatCard } from "@/components/dashboard/stat-card";
import { Card, CardContent } from "@/components/ui/card";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { endpoints, queryKeys } from "@/lib/api/queries";
import { formatNumber, formatPercent, titleCase } from "@/lib/utils";

const RANGES = [
  { value: 14, label: "Last 14 days" },
  { value: 30, label: "Last 30 days" },
  { value: 90, label: "Last 90 days" },
];

const AXIS = "hsl(var(--chart-axis))";
const GRID = "hsl(var(--chart-grid))";

function shortDate(value: string): string {
  const date = new Date(`${value}T00:00:00`);
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export default function AnalyticsPage() {
  const [days, setDays] = useState(30);
  const analytics = useQuery({
    queryKey: queryKeys.analytics(days),
    queryFn: () => endpoints.analytics(days),
  });

  if (analytics.isLoading || !analytics.data) {
    return (
      <div className="mx-auto max-w-6xl space-y-4">
        <Skeleton className="h-9 w-40" />
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-72 w-full" />
      </div>
    );
  }

  const report = analytics.data;
  const series = report.applications_per_day.map((point) => ({
    ...point,
    label: shortDate(point.date),
  }));
  const hasActivity = series.some((point) => point.created > 0 || point.submitted > 0);

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Analytics</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Everything here is counted from your own applications. Nothing is estimated.
          </p>
        </div>
        <div className="w-44">
          <Select
            aria-label="Time range"
            value={String(days)}
            onChange={(event) => setDays(Number(event.target.value))}
          >
            {RANGES.map((range) => (
              <option key={range.value} value={range.value}>
                {range.label}
              </option>
            ))}
          </Select>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Applications sent"
          value={formatNumber(report.outcomes.submitted)}
          hint={`${formatNumber(report.automation.unconfirmed)} unconfirmed`}
        />
        <StatCard
          label="Response rate"
          value={formatPercent(report.outcomes.response_rate)}
          hint={`${formatNumber(report.outcomes.responses)} replies`}
          tone={report.outcomes.response_rate >= 20 ? "success" : "default"}
        />
        <StatCard
          label="Interviews"
          value={formatNumber(report.outcomes.interviews)}
          hint={`${formatNumber(report.outcomes.offers)} offers`}
          tone={report.outcomes.interviews > 0 ? "success" : "default"}
        />
        <StatCard
          label="Automation success"
          value={formatPercent(report.automation.success_rate)}
          hint={`${formatNumber(report.automation.awaiting_user)} waiting on you`}
          tone={report.automation.failure_rate > 25 ? "warning" : "default"}
        />
      </div>

      <ChartFrame
        title="Applications over time"
        description="Created versus actually submitted, per day."
        columns={["Day", "Created", "Submitted"]}
        rows={series.map((point) => [point.label, point.created, point.submitted])}
        empty={!hasActivity}
        emptyMessage="No applications in this window yet."
      >
        <ResponsiveContainer width="100%" height={260}>
          <AreaChart data={series} margin={{ top: 8, right: 8, bottom: 0, left: -20 }}>
            <defs>
              <linearGradient id="createdFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--chart-1)" stopOpacity={0.25} />
                <stop offset="100%" stopColor="var(--chart-1)" stopOpacity={0.02} />
              </linearGradient>
              <linearGradient id="submittedFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--chart-2)" stopOpacity={0.25} />
                <stop offset="100%" stopColor="var(--chart-2)" stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke={GRID} strokeDasharray="3 3" vertical={false} />
            <XAxis
              dataKey="label"
              stroke={AXIS}
              tickLine={false}
              axisLine={false}
              fontSize={11}
              minTickGap={24}
            />
            <YAxis
              stroke={AXIS}
              tickLine={false}
              axisLine={false}
              fontSize={11}
              allowDecimals={false}
              width={40}
            />
            <Tooltip content={<ChartTooltip />} cursor={{ stroke: GRID }} />
            <Legend iconType="square" wrapperStyle={{ fontSize: 12, paddingTop: 8 }} />
            <Area
              type="monotone"
              dataKey="created"
              name="Created"
              stroke="var(--chart-1)"
              strokeWidth={2}
              fill="url(#createdFill)"
            />
            <Area
              type="monotone"
              dataKey="submitted"
              name="Submitted"
              stroke="var(--chart-2)"
              strokeWidth={2}
              fill="url(#submittedFill)"
            />
          </AreaChart>
        </ResponsiveContainer>
      </ChartFrame>

      <div className="grid gap-6 lg:grid-cols-2">
        <ChartFrame
          title="Funnel"
          description="From discovered to offer."
          columns={["Stage", "Count"]}
          rows={report.funnel.map((stage) => [stage.label, stage.count])}
        >
          <ResponsiveContainer width="100%" height={220}>
            <BarChart
              data={report.funnel}
              layout="vertical"
              margin={{ top: 4, right: 24, bottom: 0, left: 8 }}
            >
              <CartesianGrid stroke={GRID} strokeDasharray="3 3" horizontal={false} />
              <XAxis
                type="number"
                stroke={AXIS}
                tickLine={false}
                axisLine={false}
                fontSize={11}
                allowDecimals={false}
              />
              <YAxis
                type="category"
                dataKey="label"
                stroke={AXIS}
                tickLine={false}
                axisLine={false}
                fontSize={11}
                width={110}
              />
              <Tooltip content={<ChartTooltip />} cursor={{ fill: GRID, fillOpacity: 0.3 }} />
              <Bar
                dataKey="count"
                name="Jobs"
                fill="var(--chart-1)"
                radius={[0, 4, 4, 0]}
                barSize={16}
              />
            </BarChart>
          </ResponsiveContainer>
        </ChartFrame>

        <ChartFrame
          title="Match score distribution"
          description="How your scored jobs are spread."
          columns={["Score", "Jobs"]}
          rows={report.match_score_distribution.map((bucket) => [bucket.label, bucket.count])}
          empty={report.match_score_distribution.every((bucket) => bucket.count === 0)}
          emptyMessage="No jobs have been scored yet."
        >
          <ResponsiveContainer width="100%" height={220}>
            <BarChart
              data={report.match_score_distribution}
              margin={{ top: 4, right: 8, bottom: 0, left: -20 }}
            >
              <CartesianGrid stroke={GRID} strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="label" stroke={AXIS} tickLine={false} axisLine={false} fontSize={11} />
              <YAxis
                stroke={AXIS}
                tickLine={false}
                axisLine={false}
                fontSize={11}
                allowDecimals={false}
                width={40}
              />
              <Tooltip content={<ChartTooltip />} cursor={{ fill: GRID, fillOpacity: 0.3 }} />
              <Bar dataKey="count" name="Jobs" radius={[4, 4, 0, 0]} barSize={36}>
                {report.match_score_distribution.map((bucket, index) => (
                  <Cell
                    key={bucket.label}
                    // Emphasis, not identity: the strongest band is the one that
                    // matters, the rest are context.
                    fill={index >= 3 ? "var(--chart-1)" : GRID}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </ChartFrame>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {[
          { title: "Applications by company", data: report.by_company, unit: "Company" },
          { title: "Applications by role", data: report.by_role, unit: "Role" },
        ].map((panel) => (
          <ChartFrame
            key={panel.title}
            title={panel.title}
            columns={[panel.unit, "Applications"]}
            rows={panel.data.map((item) => [titleCase(item.label), item.count])}
            empty={panel.data.length === 0}
          >
            <ResponsiveContainer width="100%" height={Math.max(160, panel.data.length * 34)}>
              <BarChart
                data={panel.data.map((item) => ({ ...item, label: titleCase(item.label) }))}
                layout="vertical"
                margin={{ top: 4, right: 24, bottom: 0, left: 8 }}
              >
                <CartesianGrid stroke={GRID} strokeDasharray="3 3" horizontal={false} />
                <XAxis
                  type="number"
                  stroke={AXIS}
                  tickLine={false}
                  axisLine={false}
                  fontSize={11}
                  allowDecimals={false}
                />
                <YAxis
                  type="category"
                  dataKey="label"
                  stroke={AXIS}
                  tickLine={false}
                  axisLine={false}
                  fontSize={11}
                  width={150}
                />
                <Tooltip content={<ChartTooltip />} cursor={{ fill: GRID, fillOpacity: 0.3 }} />
                <Bar
                  dataKey="count"
                  name="Applications"
                  fill="var(--chart-1)"
                  radius={[0, 4, 4, 0]}
                  barSize={16}
                />
              </BarChart>
            </ResponsiveContainer>
          </ChartFrame>
        ))}
      </div>

      <Card>
        <CardContent className="grid gap-4 p-5 sm:grid-cols-4">
          {[
            ["Succeeded", report.automation.succeeded],
            ["Failed", report.automation.failed],
            ["Waiting on you", report.automation.awaiting_user],
            ["Unconfirmed", report.automation.unconfirmed],
          ].map(([label, value]) => (
            <div key={label as string}>
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                {label as string}
              </p>
              <p className="mt-1 text-xl font-semibold tabular">{formatNumber(value as number)}</p>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
