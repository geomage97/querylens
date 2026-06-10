"use client";

// Schema explorer: the auto-discovered structure of the active connection.
// React Query's queryKey includes the connection id, so switching connections
// fetches (and caches) each schema separately.

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { getSchema } from "@/lib/api";
import { useConnection } from "@/components/providers";
import { EngineBadge } from "@/components/engine-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { Skeleton } from "@/components/ui/skeleton";
import type { FieldInfo } from "@/lib/types";
import { ChevronRight, Link2, RefreshCw, Table2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

function FieldRow({ name, info }: { name: string; info: FieldInfo }) {
  return (
    <div className="flex items-start gap-3 border-t px-4 py-2 text-sm first:border-t-0">
      <span className="w-56 shrink-0 truncate font-mono text-xs" title={name}>
        {name}
      </span>
      <span className="shrink-0 font-mono text-xs text-muted-foreground">
        {info.types.join(" | ")}
        {info.nullable ? "?" : ""}
      </span>
      <span className="min-w-0 flex-1 truncate text-xs text-muted-foreground">
        {info.values ? (
          <span className="flex flex-wrap gap-1">
            {info.values.slice(0, 8).map((v) => (
              <Badge key={String(v)} variant="secondary" className="px-1.5 py-0 text-[10px]">
                {String(v)}
              </Badge>
            ))}
          </span>
        ) : info.examples ? (
          `e.g. ${info.examples.map((e) => JSON.stringify(e)).join(", ")}`
        ) : null}
      </span>
    </div>
  );
}

export default function SchemaPage() {
  const { active } = useConnection();
  const queryClient = useQueryClient();
  const [refreshing, setRefreshing] = useState(false);

  const { data: schema, isLoading } = useQuery({
    queryKey: ["schema", active?.connection_id],
    queryFn: () => getSchema(active!.connection_id),
    enabled: active !== null, // don't fetch until a connection is selected
  });

  async function refresh() {
    if (!active) return;
    setRefreshing(true);
    try {
      const fresh = await getSchema(active.connection_id, true);
      queryClient.setQueryData(["schema", active.connection_id], fresh);
      toast.success("Schema re-discovered from the live database");
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setRefreshing(false);
    }
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6 px-8 py-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="flex items-center gap-3 text-xl font-semibold">
            Schema
            {active && <EngineBadge engine={active.engine} />}
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {active
              ? `Auto-discovered structure of ${active.name} / ${active.database}.`
              : "Select a connection in the sidebar."}
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          className="gap-1.5"
          onClick={refresh}
          disabled={!active || refreshing}
        >
          <RefreshCw className={`size-3.5 ${refreshing ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </div>

      {(isLoading || refreshing) && (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-14" />
          ))}
        </div>
      )}

      <div className="space-y-3">
        {schema?.entities.map((entity) => (
          <Collapsible key={entity.name} defaultOpen={schema.entities.length <= 6}>
            <Card className="overflow-hidden py-0 gap-0">
              <CollapsibleTrigger className="w-full">
                <CardHeader className="flex-row items-center px-4 py-3 hover:bg-accent/40">
                  <CardTitle className="flex w-full items-center gap-2.5 text-sm font-medium">
                    <ChevronRight className="size-4 text-muted-foreground transition-transform [[data-state=open]_&]:rotate-90" />
                    <Table2 className="size-4 text-muted-foreground" />
                    <span className="font-mono">{entity.name}</span>
                    <span className="text-xs font-normal text-muted-foreground">
                      ~{entity.approx_count.toLocaleString()} {schema.engine === "mongodb" ? "documents" : "rows"}
                      {" · "}
                      {Object.keys(entity.fields).length} fields
                    </span>
                    {entity.foreign_keys && (
                      <Badge variant="outline" className="ml-auto gap-1 text-[10px]">
                        <Link2 className="size-3" />
                        {entity.foreign_keys.length} FK
                      </Badge>
                    )}
                  </CardTitle>
                </CardHeader>
              </CollapsibleTrigger>
              <CollapsibleContent>
                <CardContent className="px-0 pb-0">
                  {entity.foreign_keys && (
                    <div className="border-t bg-muted/30 px-4 py-2">
                      {entity.foreign_keys.map((fk) => (
                        <div key={fk} className="font-mono text-xs text-muted-foreground">
                          <Link2 className="mr-1.5 inline size-3" />
                          {fk}
                        </div>
                      ))}
                    </div>
                  )}
                  {Object.entries(entity.fields).map(([name, info]) => (
                    <FieldRow key={name} name={name} info={info} />
                  ))}
                </CardContent>
              </CollapsibleContent>
            </Card>
          </Collapsible>
        ))}
      </div>
    </div>
  );
}
