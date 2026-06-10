"use client";

import { Loader2, RotateCcw } from "lucide-react";

const STAGE_LABELS: Record<string, string> = {
  generating_query: "Generating query",
  executing: "Running query",
  retrying: "Query failed — correcting and retrying",
  formatting: "Writing answer",
};

export function StageIndicator({ stage }: { stage: string }) {
  const Icon = stage === "retrying" ? RotateCcw : Loader2;
  return (
    <span className="flex items-center gap-2 text-sm text-muted-foreground">
      <Icon className={`size-3.5 ${stage === "retrying" ? "text-amber-400" : "animate-spin"}`} />
      {STAGE_LABELS[stage] ?? stage}…
    </span>
  );
}
