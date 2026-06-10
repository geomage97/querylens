// The single place the frontend talks to the backend. Every page imports
// functions from here instead of calling fetch() directly — so URLs, error
// handling, and types live in one spot.

import type {
  CardRunResult,
  Connection,
  DashboardCard,
  Engine,
  Schema,
  SessionMessage,
  SessionSummary,
  StreamEvent,
  VisualizationHint,
} from "@/lib/types";

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      // non-JSON error body; keep statusText
    }
    throw new Error(detail);
  }
  return res.json();
}

// -- Connections --------------------------------------------------------------

export async function listConnections(): Promise<Connection[]> {
  const body = await request<{ connections: Connection[] }>("/connections");
  return body.connections;
}

export function addConnection(input: {
  name: string;
  engine: Engine;
  uri: string;
  database: string;
}): Promise<Connection> {
  return request("/connections", { method: "POST", body: JSON.stringify(input) });
}

export function deleteConnection(connectionId: string): Promise<{ ok: boolean }> {
  return request(`/connections/${connectionId}`, { method: "DELETE" });
}

export function testConnection(
  connectionId: string,
): Promise<{ ok: boolean; message: string }> {
  return request(`/connections/${connectionId}/test`, { method: "POST" });
}

export function getSchema(connectionId: string, refresh = false): Promise<Schema> {
  return request(`/connections/${connectionId}/schema${refresh ? "?refresh=true" : ""}`);
}

// -- Sessions -----------------------------------------------------------------

export async function listSessions(limit = 30): Promise<SessionSummary[]> {
  const body = await request<{ sessions: SessionSummary[] }>(`/sessions?limit=${limit}`);
  return body.sessions;
}

export function deleteSession(sessionId: string): Promise<{ ok: boolean }> {
  return request(`/sessions/${sessionId}`, { method: "DELETE" });
}

export async function getSessionMessages(sessionId: string): Promise<SessionMessage[]> {
  // The backend stores history per session; expose it through the sessions list
  // until a dedicated endpoint exists. (GET /sessions returns previews only, so
  // resuming loads history lazily via this helper.)
  const body = await request<{ messages: SessionMessage[] }>(`/sessions/${sessionId}/messages`);
  return body.messages;
}

// -- Dashboard ------------------------------------------------------------------

export async function listCards(): Promise<DashboardCard[]> {
  const body = await request<{ cards: DashboardCard[] }>("/dashboard/cards");
  return body.cards;
}

export function addCard(input: {
  title: string;
  question: string;
  connection_id: string;
  generated_query: Record<string, unknown>;
  visualization_hint: VisualizationHint;
}): Promise<DashboardCard> {
  return request("/dashboard/cards", { method: "POST", body: JSON.stringify(input) });
}

export function deleteCard(cardId: string): Promise<{ ok: boolean }> {
  return request(`/dashboard/cards/${cardId}`, { method: "DELETE" });
}

export function runCard(cardId: string): Promise<CardRunResult> {
  return request(`/dashboard/cards/${cardId}/run`, { method: "POST" });
}

// -- Chat (streaming) -----------------------------------------------------------

// EventSource only supports GET, so we POST with fetch and parse the SSE
// format ("event: X\ndata: {...}\n\n") off the response body stream ourselves.
export async function* streamChat(
  question: string,
  connectionId: string,
  sessionId?: string,
  signal?: AbortSignal,
): AsyncGenerator<StreamEvent> {
  const res = await fetch(`${API_URL}/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question,
      connection_id: connectionId,
      session_id: sessionId ?? null,
    }),
    signal,
  });
  if (!res.ok || !res.body) {
    throw new Error(`Stream failed: ${res.status} ${res.statusText}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // SSE messages are separated by a blank line
    let sep: number;
    while ((sep = buffer.indexOf("\n\n")) !== -1) {
      const raw = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);

      let event = "message";
      let data = "";
      for (const line of raw.split("\n")) {
        if (line.startsWith("event: ")) event = line.slice(7).trim();
        else if (line.startsWith("data: ")) data += line.slice(6);
      }
      if (data) {
        yield { event, data: JSON.parse(data) } as StreamEvent;
      }
    }
  }
}
