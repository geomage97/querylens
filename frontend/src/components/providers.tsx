"use client";

// React pattern: "providers" wrap the whole app and make shared state available
// to any component below them via React context — no prop-drilling.
// This file is a client component ("use client") because providers hold state.

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createContext, useContext, useEffect, useState } from "react";
import type { Connection } from "@/lib/types";
import { listConnections } from "@/lib/api";
import { useQuery } from "@tanstack/react-query";

// One QueryClient for the app. React Query caches every server response by its
// "query key", deduplicates identical requests, and refetches stale data.
const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 30_000, retry: 1, refetchOnWindowFocus: false },
  },
});

// -- Active connection context -------------------------------------------------
// The connection switcher in the sidebar sets this; chat and schema pages read it.

interface ConnectionContextValue {
  connections: Connection[];
  isLoading: boolean;
  active: Connection | null;
  setActiveId: (id: string) => void;
}

const ConnectionContext = createContext<ConnectionContextValue>({
  connections: [],
  isLoading: true,
  active: null,
  setActiveId: () => {},
});

export function useConnection() {
  return useContext(ConnectionContext);
}

function ConnectionProvider({ children }: { children: React.ReactNode }) {
  const { data: connections = [], isLoading } = useQuery({
    queryKey: ["connections"],
    queryFn: listConnections,
  });

  const [activeId, setActiveId] = useState<string | null>(null);

  // Remember the chosen connection across page reloads
  useEffect(() => {
    const saved = localStorage.getItem("querylens.connection");
    if (saved) setActiveId(saved);
  }, []);

  const persistActiveId = (id: string) => {
    setActiveId(id);
    localStorage.setItem("querylens.connection", id);
  };

  const active =
    connections.find((c) => c.connection_id === activeId) ?? connections[0] ?? null;

  return (
    <ConnectionContext.Provider
      value={{ connections, isLoading, active, setActiveId: persistActiveId }}
    >
      {children}
    </ConnectionContext.Provider>
  );
}

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>
      <ConnectionProvider>{children}</ConnectionProvider>
    </QueryClientProvider>
  );
}
