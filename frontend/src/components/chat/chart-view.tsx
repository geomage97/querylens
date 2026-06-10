"use client";

// Charts from query results (Recharts). The interesting part is inference:
// results arrive as arbitrary rows, so we pick the first non-numeric column
// as the label/x-axis and every numeric column as a series. If nothing
// numeric exists there's nothing to chart and the caller falls back to a table.

import { useMemo } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { VisualizationHint } from "@/lib/types";

type Row = Record<string, unknown>;

const PALETTE = [
  "#34d399", "#38bdf8", "#a78bfa", "#fbbf24", "#f87171",
  "#2dd4bf", "#fb923c", "#e879f9", "#a3e635", "#94a3b8",
];

const MAX_BAR_POINTS = 24;
const MAX_PIE_SLICES = 10;

export function inferChart(rows: Row[]) {
  if (rows.length < 2) return null;
  const sample = rows[0];
  const keys = Object.keys(sample);
  const numeric = keys.filter((k) =>
    rows.every((r) => r[k] === null || typeof r[k] === "number"),
  );
  // Label axis: first non-numeric column, or (all-numeric results, e.g.
  // year/count) the first column. Never plot the label as a series too.
  const label = keys.find((k) => !numeric.includes(k)) ?? keys[0];
  const series = numeric.filter((k) => k !== label).slice(0, 4);
  if (series.length === 0 || !label) return null;
  return { label, series };
}

const axisStyle = { fontSize: 11, fill: "var(--muted-foreground)" };
const tooltipStyle = {
  backgroundColor: "var(--popover)",
  border: "1px solid var(--border)",
  borderRadius: 8,
  fontSize: 12,
};

export function ChartView({ data, hint }: { data: Row[]; hint: VisualizationHint }) {
  const shape = useMemo(() => inferChart(data), [data]);
  const rows = useMemo(() => {
    if (!shape) return [];
    const limit = hint === "pie_chart" ? MAX_PIE_SLICES : MAX_BAR_POINTS;
    return data.slice(0, limit).map((r) => ({ ...r, [shape.label]: String(r[shape.label]) }));
  }, [data, shape, hint]);

  if (!shape) return null;
  const { label, series } = shape;

  if (hint === "pie_chart") {
    return (
      <ResponsiveContainer width="100%" height={280}>
        <PieChart>
          <Pie
            data={rows}
            dataKey={series[0]}
            nameKey={label}
            innerRadius={55}
            outerRadius={100}
            paddingAngle={2}
            stroke="none"
          >
            {rows.map((_, i) => (
              <Cell key={i} fill={PALETTE[i % PALETTE.length]} />
            ))}
          </Pie>
          <Tooltip contentStyle={tooltipStyle} />
          <Legend wrapperStyle={{ fontSize: 12 }} />
        </PieChart>
      </ResponsiveContainer>
    );
  }

  if (hint === "line_chart") {
    return (
      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={rows} margin={{ left: 8, right: 16, top: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
          <XAxis dataKey={label} tick={axisStyle} tickLine={false} />
          <YAxis tick={axisStyle} tickLine={false} axisLine={false} width={70} />
          <Tooltip contentStyle={tooltipStyle} />
          {series.length > 1 && <Legend wrapperStyle={{ fontSize: 12 }} />}
          {series.map((s, i) => (
            <Line
              key={s}
              type="monotone"
              dataKey={s}
              stroke={PALETTE[i % PALETTE.length]}
              strokeWidth={2}
              dot={rows.length <= 30}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    );
  }

  // default: bar chart
  return (
    <ResponsiveContainer width="100%" height={280}>
      <BarChart data={rows} margin={{ left: 8, right: 16, top: 8 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
        <XAxis
          dataKey={label}
          tick={axisStyle}
          tickLine={false}
          interval={0}
          angle={rows.length > 8 ? -30 : 0}
          textAnchor={rows.length > 8 ? "end" : "middle"}
          height={rows.length > 8 ? 70 : 30}
        />
        <YAxis tick={axisStyle} tickLine={false} axisLine={false} width={70} />
        <Tooltip contentStyle={tooltipStyle} cursor={{ fill: "var(--accent)" }} />
        {series.length > 1 && <Legend wrapperStyle={{ fontSize: 12 }} />}
        {series.map((s, i) => (
          <Bar key={s} dataKey={s} fill={PALETTE[i % PALETTE.length]} radius={[4, 4, 0, 0]} />
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}
