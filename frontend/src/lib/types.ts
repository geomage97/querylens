// TypeScript mirrors of the backend's Pydantic models (backend/app/api/models.py).
// Keeping these in one file means the whole app agrees on the API's shape.

export type Engine = "mongodb" | "postgresql";

export interface Connection {
  connection_id: string;
  name: string;
  engine: Engine;
  database: string;
  uri_masked: string;
  created_at: string | null;
}

export interface FieldInfo {
  types: string[];
  examples?: unknown[];
  values?: unknown[]; // present for enum-like fields
  nullable?: boolean;
}

export interface SchemaEntity {
  name: string;
  approx_count: number;
  fields: Record<string, FieldInfo>;
  foreign_keys?: string[];
}

export interface Schema {
  engine: Engine;
  entities: SchemaEntity[];
}

export type VisualizationHint =
  | "table"
  | "number"
  | "list"
  | "bar_chart"
  | "pie_chart"
  | "none";

export interface TokenStats {
  input: number;
  output: number;
  cache_read: number;
  cache_creation: number;
}

export interface ChatResult {
  answer: string;
  data: Record<string, unknown>[] | Record<string, unknown> | null;
  visualization_hint: VisualizationHint;
  record_count: number;
  query_summary: string;
  generated_query: Record<string, unknown> | null;
  retried: boolean;
  duration_ms: number | null;
  model_used: string | null;
  tokens: TokenStats | null;
  session_id?: string;
  connection_id?: string;
}

export interface SessionSummary {
  session_id: string;
  connection_id: string | null;
  updated_at: string | null;
  message_count: number;
  preview: string;
}

export interface SessionMessage {
  role: "user" | "assistant";
  content: string;
}

// Events emitted by POST /chat/stream (Server-Sent Events)
export type StreamEvent =
  | { event: "session"; data: { session_id: string; connection_id: string } }
  | { event: "status"; data: { stage: string; error?: string } }
  | { event: "query"; data: Record<string, unknown> }
  | { event: "delta"; data: { text: string } }
  | { event: "result"; data: ChatResult }
  | { event: "done"; data: Record<string, never> };
