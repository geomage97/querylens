import { Badge } from "@/components/ui/badge";
import type { Engine } from "@/lib/types";
import { Database, Leaf } from "lucide-react";

const STYLES: Record<Engine, { label: string; className: string }> = {
  mongodb: {
    label: "MongoDB",
    className: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
  },
  postgresql: {
    label: "PostgreSQL",
    className: "bg-sky-500/15 text-sky-400 border-sky-500/30",
  },
};

export function EngineBadge({ engine }: { engine: Engine }) {
  const s = STYLES[engine];
  const Icon = engine === "mongodb" ? Leaf : Database;
  return (
    <Badge variant="outline" className={`gap-1 font-medium ${s.className}`}>
      <Icon className="size-3" />
      {s.label}
    </Badge>
  );
}
