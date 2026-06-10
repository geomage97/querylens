# Frontend notes — the React patterns used here, explained

A tour of the ideas in this codebase, written for someone new to React. Each
pattern names the files where you can see it in action.

## 1. Components are functions that return UI

Everything on screen is a function returning JSX (HTML-like syntax). Big
screens are composed from small components: the chat page
([chat-panel.tsx](src/components/chat/chat-panel.tsx)) renders `<Message>`,
which renders `<ResultsTable>` and `<QueryInspector>`. Props flow downward —
a component receives data from its parent as function arguments.

## 2. Server vs client components (Next.js App Router)

By default, App Router components render on the server — fast, but no
interactivity. Anything using state, effects, or browser APIs needs
`"use client"` at the top of the file. Rule of thumb here: pages and layout
stay lean; interactive widgets are client components.

## 3. State: `useState` and immutability

`useState` declares a value React watches; calling its setter re-renders the
component. React only notices *replaced* values, never mutated ones — which is
why [chat-panel.tsx](src/components/chat/chat-panel.tsx) updates the streaming
message with `msgs.map(...)` (builds a new array) instead of editing in place.

## 4. Server state: React Query instead of hand-rolled fetching

For data that lives on the backend, `useQuery` beats `useState` + `fetch` +
`useEffect`: it caches by `queryKey`, dedupes identical requests, tracks
`isLoading`, and refetches stale data. Writes use `useMutation`, and after a
successful write we call `invalidateQueries` so every list refreshes itself —
see [connections/page.tsx](src/app/connections/page.tsx) and
[session-panel.tsx](src/components/chat/session-panel.tsx).
The `queryKey` is the cache identity: `["schema", connectionId]` caches each
connection's schema separately ([schema/page.tsx](src/app/schema/page.tsx)).

## 5. Context: app-wide state without prop-drilling

The active connection is needed by the sidebar, chat, and schema pages.
Passing it down through every component ("prop-drilling") gets miserable, so
[providers.tsx](src/components/providers.tsx) puts it in a React context;
any component calls `useConnection()` to read it. The choice persists in
`localStorage` so a refresh keeps your selection.

## 6. Streaming UI: async generators driving state

The chat consumes `/chat/stream` (Server-Sent Events) through an async
generator ([api.ts](src/lib/api.ts) `streamChat`). Each yielded event patches
the last message in state, so the answer assembles live: stage indicator ->
generated query -> token-by-token text -> final table. EventSource only
supports GET, so we POST with `fetch` and parse the `event:`/`data:` lines off
the response body ourselves.

## 7. Derived data: `useMemo`

Sorting result rows on every keystroke would be wasteful.
[results-table.tsx](src/components/chat/results-table.tsx) wraps sorting in
`useMemo(...)`, which recomputes only when the rows or the sort column change.

## 8. One API module

Every backend call goes through [api.ts](src/lib/api.ts), and every API shape
is typed once in [types.ts](src/lib/types.ts) — mirrors of the backend's
Pydantic models. Pages never call `fetch` directly, so error handling and the
base URL live in exactly one place.

## 9. shadcn/ui: owned components, not a dependency

`npx shadcn add button` copies the component's source into
`src/components/ui/` — you own and can edit it. This generation of shadcn is
built on Base UI: composition uses a `render` prop
(`<DialogTrigger render={<Button />}>`), unlike the older Radix-based
`asChild` pattern you'll see in most tutorials.

## 10. Charts from arbitrary data: inference + composition (Recharts)

[chart-view.tsx](src/components/chat/chart-view.tsx) can't know the result
columns in advance, so `inferChart` picks the first non-numeric column as the
label axis and the numeric columns as series. Recharts is *compositional*:
a chart is JSX (`<BarChart><XAxis/><Bar/></BarChart>`), so swapping bar/line/
pie is just rendering different children. `ResponsiveContainer` makes the
chart fill whatever space its parent gives it.

## 11. Independent data per component instance

Each dashboard card ([dashboard/page.tsx](src/app/dashboard/page.tsx)) calls
`useQuery` with its own key (`["card-run", card.card_id]`). Hooks belong to a
component *instance*, so ten cards means ten independent queries — each one
loads, refreshes, and fails on its own without any coordination code. That's
the React mental model in one example: state and effects scale by composing
components, not by writing a manager.
