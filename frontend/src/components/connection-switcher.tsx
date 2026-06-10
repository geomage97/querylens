"use client";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { useConnection } from "@/components/providers";
import { Database, Leaf } from "lucide-react";

export function ConnectionSwitcher() {
  const { connections, isLoading, active, setActiveId } = useConnection();

  if (isLoading) return <Skeleton className="h-9 w-full" />;
  if (connections.length === 0) {
    return (
      <div className="rounded-md border border-dashed px-3 py-2 text-xs text-muted-foreground">
        No connections
      </div>
    );
  }

  return (
    <Select
      value={active?.connection_id}
      onValueChange={(v) => v && setActiveId(v)}
    >
      <SelectTrigger className="w-full" aria-label="Active connection">
        <SelectValue>
          {active ? (
            <span className="flex items-center gap-2">
              {active.engine === "mongodb" ? (
                <Leaf className="size-3.5 text-emerald-400" />
              ) : (
                <Database className="size-3.5 text-sky-400" />
              )}
              {active.name}
            </span>
          ) : (
            "Pick a connection"
          )}
        </SelectValue>
      </SelectTrigger>
      <SelectContent>
        {connections.map((c) => (
          <SelectItem key={c.connection_id} value={c.connection_id}>
            <span className="flex items-center gap-2">
              {c.engine === "mongodb" ? (
                <Leaf className="size-3.5 text-emerald-400" />
              ) : (
                <Database className="size-3.5 text-sky-400" />
              )}
              {c.name}
            </span>
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
