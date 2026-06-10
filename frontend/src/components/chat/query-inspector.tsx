"use client";

// Collapsible "under the hood" panel for each answer: the exact query that ran,
// how long it took, and what it cost in tokens.

import { useState } from "react";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import type { ChatResult } from "@/lib/types";
import { ChevronRight, Code2 } from "lucide-react";

function formatQuery(query: Record<string, unknown>): string {
  // SQL reads better raw; MongoDB queries read better as pretty JSON
  if (typeof query.sql === "string") return query.sql;
  const { visualization_hint, query_summary, ...rest } = query;
  void visualization_hint;
  void query_summary;
  return JSON.stringify(rest, null, 2);
}

export function QueryInspector({ result }: { result: ChatResult }) {
  const [open, setOpen] = useState(false);
  if (!result.generated_query) return null;

  const tokens = result.tokens;
  const stats = [
    result.duration_ms != null ? `${(result.duration_ms / 1000).toFixed(1)}s` : null,
    tokens ? `${(tokens.input + tokens.cache_read).toLocaleString()} in / ${tokens.output.toLocaleString()} out` : null,
    tokens && tokens.cache_read > 0 ? `${tokens.cache_read.toLocaleString()} cached` : null,
    result.model_used,
    result.retried ? "retried once" : null,
  ].filter(Boolean);

  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <CollapsibleTrigger className="flex w-full items-center gap-1.5 text-xs text-muted-foreground transition-colors hover:text-foreground">
        <ChevronRight className={`size-3 transition-transform ${open ? "rotate-90" : ""}`} />
        <Code2 className="size-3" />
        Query inspector
        <span className="ml-auto font-mono text-[11px]">{stats.join(" · ")}</span>
      </CollapsibleTrigger>
      <CollapsibleContent>
        <pre className="mt-2 max-h-64 overflow-auto rounded-md border bg-muted/40 p-3 font-mono text-xs leading-relaxed">
          {formatQuery(result.generated_query)}
        </pre>
        {result.query_summary && (
          <p className="mt-1.5 text-xs italic text-muted-foreground">
            {result.query_summary}
          </p>
        )}
      </CollapsibleContent>
    </Collapsible>
  );
}
