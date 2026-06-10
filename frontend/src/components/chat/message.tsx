"use client";

import { useMemo, useState } from "react";
import type { ChatResult } from "@/lib/types";
import { ChartView, inferChart } from "@/components/chat/chart-view";
import { PinDialog } from "@/components/chat/pin-dialog";
import { QueryInspector } from "@/components/chat/query-inspector";
import { ResultsTable } from "@/components/chat/results-table";
import { StageIndicator } from "@/components/chat/stage-indicator";
import { Button } from "@/components/ui/button";
import { BarChart3, ScanSearch, Table2 } from "lucide-react";

// One UI message. Assistant messages grow as the stream progresses:
// stage indicator -> streamed text -> final result (chart/table + inspector).
export interface UiMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  question?: string; // for assistant messages: the question that produced them
  stage?: string | null;
  result?: ChatResult;
}

const CHART_HINTS = new Set(["bar_chart", "pie_chart", "line_chart"]);

function MetricCards({ data }: { data: Record<string, unknown> }) {
  const entries = Object.entries(data).slice(0, 6);
  return (
    <div className="flex flex-wrap gap-3">
      {entries.map(([k, v]) => (
        <div key={k} className="rounded-lg border bg-muted/30 px-4 py-3">
          <div className="text-xs text-muted-foreground">{k}</div>
          <div className="mt-0.5 font-mono text-xl font-semibold">
            {typeof v === "number" ? v.toLocaleString() : String(v)}
          </div>
        </div>
      ))}
    </div>
  );
}

function ResultBody({ result, question }: { result: ChatResult; question: string }) {
  const rows = Array.isArray(result.data)
    ? (result.data as Record<string, unknown>[])
    : null;
  const single =
    result.data && !Array.isArray(result.data)
      ? (result.data as Record<string, unknown>)
      : null;

  // Chart only when the hint asks for one AND the rows actually chart cleanly;
  // otherwise gracefully fall back to the table.
  const chartable = useMemo(
    () =>
      rows !== null && CHART_HINTS.has(result.visualization_hint) && inferChart(rows) !== null,
    [rows, result.visualization_hint],
  );
  const [view, setView] = useState<"chart" | "table">("chart");

  if (single) return <MetricCards data={single} />;
  if (!rows || rows.length === 0) return null;

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-1">
        {chartable && (
          <>
            <Button
              variant={view === "chart" ? "secondary" : "ghost"}
              size="sm"
              className="h-7 gap-1 text-xs"
              onClick={() => setView("chart")}
            >
              <BarChart3 className="size-3" /> Chart
            </Button>
            <Button
              variant={view === "table" ? "secondary" : "ghost"}
              size="sm"
              className="h-7 gap-1 text-xs"
              onClick={() => setView("table")}
            >
              <Table2 className="size-3" /> Table
            </Button>
          </>
        )}
        <span className="ml-auto">
          <PinDialog result={result} question={question} />
        </span>
      </div>
      {chartable && view === "chart" ? (
        <ChartView data={rows} hint={result.visualization_hint} />
      ) : (
        <ResultsTable data={rows} />
      )}
    </div>
  );
}

export function Message({ message }: { message: UiMessage }) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] rounded-2xl rounded-br-sm bg-primary px-4 py-2.5 text-sm text-primary-foreground">
          {message.text}
        </div>
      </div>
    );
  }

  const result = message.result;

  return (
    <div className="flex gap-3">
      <div className="mt-1 flex size-7 shrink-0 items-center justify-center rounded-lg bg-muted">
        <ScanSearch className="size-3.5 text-muted-foreground" />
      </div>
      <div className="min-w-0 flex-1 space-y-3 rounded-2xl rounded-tl-sm border bg-card px-4 py-3">
        {message.stage && <StageIndicator stage={message.stage} />}
        {message.text && (
          <p className="whitespace-pre-wrap text-sm leading-relaxed">{message.text}</p>
        )}
        {result && <ResultBody result={result} question={message.question ?? ""} />}
        {result && <QueryInspector result={result} />}
      </div>
    </div>
  );
}
