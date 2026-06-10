"use client";

// The dashboard: every card re-runs its saved query for fresh data — no LLM
// involved. React pattern worth noticing: each <DashboardCardView> owns its
// own useQuery keyed by card id, so cards load, refresh, and error
// independently of each other.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { deleteCard, listCards, runCard } from "@/lib/api";
import { useConnection } from "@/components/providers";
import { ChartView, inferChart } from "@/components/chat/chart-view";
import { ResultsTable } from "@/components/chat/results-table";
import { EngineBadge } from "@/components/engine-badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { DashboardCard } from "@/lib/types";
import { LayoutDashboard, MessageSquare, RefreshCw, X } from "lucide-react";
import { toast } from "sonner";

const CHART_HINTS = new Set(["bar_chart", "pie_chart", "line_chart"]);

function DashboardCardView({ card }: { card: DashboardCard }) {
  const { connections } = useConnection();
  const queryClient = useQueryClient();
  const connection = connections.find((c) => c.connection_id === card.connection_id);

  const run = useQuery({
    queryKey: ["card-run", card.card_id],
    queryFn: () => runCard(card.card_id),
    staleTime: 60_000,
  });

  const remove = useMutation({
    mutationFn: () => deleteCard(card.card_id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["cards"] });
      toast.success("Card removed");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const rows = run.data?.data ?? [];
  const chartable = CHART_HINTS.has(card.visualization_hint) && inferChart(rows) !== null;

  return (
    <Card className="gap-3">
      <CardHeader className="pb-0">
        <CardTitle className="flex items-start gap-2 text-sm font-medium">
          <span className="min-w-0">
            <span className="block truncate">{card.title}</span>
            <span className="mt-1 flex items-center gap-2 text-xs font-normal text-muted-foreground">
              {connection && <EngineBadge engine={connection.engine} />}
              {connection?.name}
              {run.data && (
                <span>· refreshed {new Date(run.data.refreshed_at).toLocaleTimeString()}</span>
              )}
            </span>
          </span>
          <span className="ml-auto flex shrink-0 gap-1">
            <Button
              variant="ghost"
              size="icon"
              className="size-7"
              onClick={() => run.refetch()}
              disabled={run.isFetching}
              aria-label="Refresh card"
            >
              <RefreshCw className={`size-3.5 ${run.isFetching ? "animate-spin" : ""}`} />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="size-7 text-muted-foreground hover:text-destructive"
              onClick={() => remove.mutate()}
              aria-label="Remove card"
            >
              <X className="size-3.5" />
            </Button>
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent>
        {run.isLoading && <Skeleton className="h-64 w-full" />}
        {run.isError && (
          <p className="py-8 text-center text-sm text-destructive">
            {(run.error as Error).message}
          </p>
        )}
        {run.data &&
          (chartable ? (
            <ChartView data={rows} hint={card.visualization_hint} />
          ) : (
            <ResultsTable data={rows} />
          ))}
      </CardContent>
    </Card>
  );
}

export default function DashboardPage() {
  const { data: cards, isLoading } = useQuery({ queryKey: ["cards"], queryFn: listCards });

  return (
    <div className="mx-auto max-w-6xl space-y-6 px-8 py-8">
      <div>
        <h1 className="flex items-center gap-2.5 text-xl font-semibold">
          <LayoutDashboard className="size-5 text-muted-foreground" />
          Dashboard
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Pinned queries, re-run live against their databases — no AI calls needed.
        </p>
      </div>

      {isLoading && (
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
          {Array.from({ length: 2 }).map((_, i) => (
            <Skeleton key={i} className="h-80" />
          ))}
        </div>
      )}

      {cards?.length === 0 && (
        <div className="flex flex-col items-center gap-3 rounded-lg border border-dashed py-16">
          <p className="text-sm text-muted-foreground">
            Nothing pinned yet. Ask a question in the chat and hit{" "}
            <span className="font-medium text-foreground">Pin</span> on the answer.
          </p>
          <Link href="/">
            <Button variant="outline" size="sm" className="gap-1.5">
              <MessageSquare className="size-3.5" /> Go to chat
            </Button>
          </Link>
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        {cards?.map((card) => (
          <DashboardCardView key={card.card_id} card={card} />
        ))}
      </div>
    </div>
  );
}
