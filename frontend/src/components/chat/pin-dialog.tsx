"use client";

// Pin an answer to the dashboard: freezes the generated query + viz hint so
// the dashboard can re-run it later without the LLM.

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { addCard } from "@/lib/api";
import type { ChatResult } from "@/lib/types";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Pin } from "lucide-react";
import { toast } from "sonner";

export function PinDialog({ result, question }: { result: ChatResult; question: string }) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState("");

  const pin = useMutation({
    mutationFn: () =>
      addCard({
        title: title.trim() || result.query_summary || question,
        question,
        connection_id: result.connection_id!,
        generated_query: result.generated_query!,
        visualization_hint: result.visualization_hint,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["cards"] });
      toast.success("Pinned to dashboard");
      setOpen(false);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  if (!result.generated_query || !result.connection_id) return null;

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        setOpen(o);
        if (o) setTitle(result.query_summary || question);
      }}
    >
      <DialogTrigger
        render={
          <Button variant="ghost" size="sm" className="h-7 gap-1 text-xs text-muted-foreground" />
        }
      >
        <Pin className="size-3" /> Pin
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Pin to dashboard</DialogTitle>
          <DialogDescription>
            The dashboard re-runs this exact query for fresh data — no AI call needed.
          </DialogDescription>
        </DialogHeader>
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            pin.mutate();
          }}
        >
          <div className="space-y-1.5">
            <Label htmlFor="card-title">Card title</Label>
            <Input
              id="card-title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              maxLength={120}
              autoFocus
            />
          </div>
          <DialogFooter>
            <Button type="submit" disabled={pin.isPending} className="gap-1.5">
              <Pin className="size-3.5" />
              {pin.isPending ? "Pinning…" : "Pin card"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
