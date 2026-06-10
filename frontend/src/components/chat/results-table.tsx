"use client";

// Renders query results as a sortable table with CSV/JSON export.
// React pattern: useMemo caches derived data (sorted rows) so we only re-sort
// when the inputs actually change, not on every render.

import { useMemo, useState } from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { ArrowDown, ArrowUp, ArrowUpDown, Download } from "lucide-react";

const PAGE_SIZE = 50;

type Row = Record<string, unknown>;

function cellText(v: unknown): string {
  if (v === null || v === undefined) return "";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

function downloadBlob(content: string, filename: string, type: string) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function toCsv(rows: Row[], columns: string[]): string {
  const escape = (s: string) =>
    /[",\n]/.test(s) ? `"${s.replaceAll('"', '""')}"` : s;
  const lines = [columns.map(escape).join(",")];
  for (const row of rows) {
    lines.push(columns.map((c) => escape(cellText(row[c]))).join(","));
  }
  return lines.join("\n");
}

export function ResultsTable({ data }: { data: Row[] }) {
  const [sort, setSort] = useState<{ col: string; dir: 1 | -1 } | null>(null);
  const [limit, setLimit] = useState(PAGE_SIZE);

  const columns = useMemo(() => {
    const cols = new Set<string>();
    for (const row of data.slice(0, 20)) Object.keys(row).forEach((k) => cols.add(k));
    return [...cols];
  }, [data]);

  const sorted = useMemo(() => {
    if (!sort) return data;
    const { col, dir } = sort;
    return [...data].sort((a, b) => {
      const av = a[col];
      const bv = b[col];
      if (typeof av === "number" && typeof bv === "number") return (av - bv) * dir;
      return cellText(av).localeCompare(cellText(bv)) * dir;
    });
  }, [data, sort]);

  const toggleSort = (col: string) =>
    setSort((s) =>
      s?.col === col ? (s.dir === 1 ? { col, dir: -1 } : null) : { col, dir: 1 },
    );

  if (data.length === 0) return null;

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-xs text-muted-foreground">
          {data.length.toLocaleString()} {data.length === 1 ? "row" : "rows"}
        </span>
        <div className="flex gap-1.5">
          <Button
            variant="ghost"
            size="sm"
            className="h-7 gap-1 text-xs"
            onClick={() => downloadBlob(toCsv(data, columns), "results.csv", "text/csv")}
          >
            <Download className="size-3" /> CSV
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="h-7 gap-1 text-xs"
            onClick={() =>
              downloadBlob(JSON.stringify(data, null, 2), "results.json", "application/json")
            }
          >
            <Download className="size-3" /> JSON
          </Button>
        </div>
      </div>

      <div className="max-h-80 overflow-auto rounded-md border">
        <Table>
          <TableHeader className="sticky top-0 bg-card">
            <TableRow>
              {columns.map((col) => (
                <TableHead key={col} className="whitespace-nowrap">
                  <button
                    className="flex items-center gap-1 hover:text-foreground"
                    onClick={() => toggleSort(col)}
                  >
                    {col}
                    {sort?.col === col ? (
                      sort.dir === 1 ? (
                        <ArrowUp className="size-3" />
                      ) : (
                        <ArrowDown className="size-3" />
                      )
                    ) : (
                      <ArrowUpDown className="size-3 opacity-30" />
                    )}
                  </button>
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {sorted.slice(0, limit).map((row, i) => (
              <TableRow key={i}>
                {columns.map((col) => (
                  <TableCell
                    key={col}
                    className="max-w-64 truncate whitespace-nowrap font-mono text-xs"
                    title={cellText(row[col])}
                  >
                    {cellText(row[col])}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      {sorted.length > limit && (
        <Button
          variant="ghost"
          size="sm"
          className="h-7 w-full text-xs"
          onClick={() => setLimit((l) => l + PAGE_SIZE)}
        >
          Show more ({sorted.length - limit} remaining)
        </Button>
      )}
    </div>
  );
}
