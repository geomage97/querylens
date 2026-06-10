"use client";

// Session history: list, resume, delete. React Query handles the fetching and
// cache invalidation — after a delete we call invalidateQueries and the list
// refetches itself.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { deleteSession, listSessions } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";
import { History, Trash2 } from "lucide-react";
import { toast } from "sonner";

export function SessionPanel({
  activeSessionId,
  onResume,
}: {
  activeSessionId: string | null;
  onResume: (sessionId: string, connectionId: string | null) => void;
}) {
  const queryClient = useQueryClient();
  const { data: sessions, isLoading } = useQuery({
    queryKey: ["sessions"],
    queryFn: () => listSessions(30),
  });

  const remove = useMutation({
    mutationFn: deleteSession,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sessions"] });
      toast.success("Conversation deleted");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <div className="flex h-full w-64 shrink-0 flex-col border-l">
      <div className="flex items-center gap-2 border-b px-4 py-3 text-sm font-medium">
        <History className="size-4 text-muted-foreground" />
        History
      </div>
      <ScrollArea className="flex-1">
        <div className="space-y-1 p-2">
          {isLoading &&
            Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          {sessions?.length === 0 && (
            <p className="px-2 py-4 text-xs text-muted-foreground">
              No conversations yet.
            </p>
          )}
          {sessions?.map((s) => (
            <div
              key={s.session_id}
              className={`group flex items-start gap-1 rounded-md px-2 py-1.5 hover:bg-accent/50 ${
                s.session_id === activeSessionId ? "bg-accent" : ""
              }`}
            >
              <button
                className="min-w-0 flex-1 text-left"
                onClick={() => onResume(s.session_id, s.connection_id)}
              >
                <div className="truncate text-xs">{s.preview || "(empty)"}</div>
                <div className="mt-0.5 text-[10px] text-muted-foreground">
                  {s.message_count / 2} {s.message_count === 2 ? "question" : "questions"}
                  {s.updated_at &&
                    ` · ${new Date(s.updated_at).toLocaleDateString()}`}
                </div>
              </button>
              <Button
                variant="ghost"
                size="icon"
                className="size-6 shrink-0 opacity-0 group-hover:opacity-100"
                onClick={() => remove.mutate(s.session_id)}
                aria-label="Delete conversation"
              >
                <Trash2 className="size-3 text-muted-foreground" />
              </Button>
            </div>
          ))}
        </div>
      </ScrollArea>
    </div>
  );
}
