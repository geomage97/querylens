"use client";

// The chat state machine. The async generator from streamChat() yields SSE
// events; each event updates the last assistant message in place, so React
// re-renders and the user watches the answer assemble: stage indicator ->
// generated query -> streamed text -> final table + inspector.

import { useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { getSessionMessages, streamChat } from "@/lib/api";
import { useConnection } from "@/components/providers";
import { Message, type UiMessage } from "@/components/chat/message";
import { SessionPanel } from "@/components/chat/session-panel";
import { EngineBadge } from "@/components/engine-badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ArrowUp, Plus } from "lucide-react";
import { toast } from "sonner";

const SUGGESTIONS = [
  "What data is available here?",
  "Show me the top 5 records by value",
  "How are records distributed per category?",
];

let nextId = 0;
const uid = () => `m${nextId++}`;

export function ChatPanel() {
  const { active, connections, setActiveId } = useConnection();
  const queryClient = useQueryClient();
  const [messages, setMessages] = useState<UiMessage[]>([]);
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Update the last (assistant) message immutably — React only re-renders
  // when state is replaced, never when it's mutated in place.
  const patchLast = (patch: Partial<UiMessage>) =>
    setMessages((msgs) =>
      msgs.map((m, i) => (i === msgs.length - 1 ? { ...m, ...patch } : m)),
    );

  // Scroll only the message list. scrollIntoView would also scroll the outer
  // <main> element and push the page header out of view.
  const scrollDown = () =>
    requestAnimationFrame(() => {
      const el = scrollRef.current;
      if (el) el.scrollTop = el.scrollHeight;
    });

  async function send(question: string) {
    if (!question.trim() || busy || !active) return;
    setInput("");
    setBusy(true);
    setMessages((m) => [
      ...m,
      { id: uid(), role: "user", text: question },
      { id: uid(), role: "assistant", text: "", question, stage: "generating_query" },
    ]);
    scrollDown();

    try {
      let answer = "";
      for await (const ev of streamChat(question, active.connection_id, sessionId ?? undefined)) {
        switch (ev.event) {
          case "session":
            setSessionId(ev.data.session_id);
            break;
          case "status":
            patchLast({ stage: ev.data.stage });
            break;
          case "delta":
            answer += ev.data.text;
            patchLast({ text: answer, stage: null });
            break;
          case "result":
            patchLast({ text: ev.data.answer, result: ev.data, stage: null });
            break;
        }
        scrollDown();
      }
      queryClient.invalidateQueries({ queryKey: ["sessions"] });
    } catch (e) {
      patchLast({ stage: null, text: `Something went wrong: ${(e as Error).message}` });
      toast.error((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function resumeSession(id: string, connectionId: string | null) {
    try {
      const history = await getSessionMessages(id);
      setSessionId(id);
      if (connectionId && connections.some((c) => c.connection_id === connectionId)) {
        setActiveId(connectionId);
      }
      setMessages(
        history.map((m) => ({ id: uid(), role: m.role, text: m.content })),
      );
      scrollDown();
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  function newChat() {
    setSessionId(null);
    setMessages([]);
  }

  return (
    <div className="flex h-screen max-h-screen">
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center gap-3 border-b px-6 py-3">
          <h1 className="text-sm font-semibold">Chat</h1>
          {active && (
            <>
              <EngineBadge engine={active.engine} />
              <span className="text-xs text-muted-foreground">
                {active.name} / {active.database}
              </span>
            </>
          )}
          <Button variant="outline" size="sm" className="ml-auto gap-1.5" onClick={newChat}>
            <Plus className="size-3.5" /> New chat
          </Button>
        </header>

        <div ref={scrollRef} className="flex-1 overflow-y-auto px-6 py-6">
          {messages.length === 0 ? (
            <div className="flex h-full flex-col items-center justify-center gap-4">
              <p className="text-lg font-medium">Ask your database anything</p>
              <p className="max-w-md text-center text-sm text-muted-foreground">
                Questions are turned into read-only{" "}
                {active?.engine === "postgresql" ? "SQL" : "MongoDB"} queries, executed,
                and explained — with the exact query shown for every answer.
              </p>
              <div className="flex flex-wrap justify-center gap-2">
                {SUGGESTIONS.map((s) => (
                  <Button key={s} variant="outline" size="sm" onClick={() => send(s)}>
                    {s}
                  </Button>
                ))}
              </div>
            </div>
          ) : (
            <div className="mx-auto max-w-3xl space-y-5">
              {messages.map((m) => (
                <Message key={m.id} message={m} />
              ))}
            </div>
          )}
        </div>

        <div className="border-t px-6 py-4">
          <form
            className="mx-auto flex max-w-3xl gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              send(input);
            }}
          >
            <Input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={
                active ? `Ask ${active.name} a question…` : "Add a connection first"
              }
              disabled={busy || !active}
              autoFocus
            />
            <Button type="submit" size="icon" disabled={busy || !input.trim() || !active}>
              <ArrowUp className="size-4" />
            </Button>
          </form>
        </div>
      </div>

      <SessionPanel activeSessionId={sessionId} onResume={resumeSession} />
    </div>
  );
}
