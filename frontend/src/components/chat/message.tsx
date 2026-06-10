"use client";

import type { ChatResult } from "@/lib/types";
import { ResultsTable } from "@/components/chat/results-table";
import { QueryInspector } from "@/components/chat/query-inspector";
import { StageIndicator } from "@/components/chat/stage-indicator";
import { ScanSearch } from "lucide-react";

// One UI message. Assistant messages grow as the stream progresses:
// stage indicator -> streamed text -> final result (table + inspector).
export interface UiMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  stage?: string | null;
  result?: ChatResult;
}

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
  const rows =
    result && Array.isArray(result.data) ? (result.data as Record<string, unknown>[]) : null;
  const single =
    result && result.data && !Array.isArray(result.data)
      ? (result.data as Record<string, unknown>)
      : null;

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
        {rows && rows.length > 0 && <ResultsTable data={rows} />}
        {single && <MetricCards data={single} />}
        {result && <QueryInspector result={result} />}
      </div>
    </div>
  );
}
