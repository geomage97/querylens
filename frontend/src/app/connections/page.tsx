"use client";

// Connections manager. React pattern: useMutation for writes — it gives us
// isPending for spinners and onSuccess/onError hooks for toasts + cache
// invalidation, mirroring how useQuery handles reads.

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { addConnection, deleteConnection, testConnection } from "@/lib/api";
import { useConnection } from "@/components/providers";
import { EngineBadge } from "@/components/engine-badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import type { Engine } from "@/lib/types";
import { CheckCircle2, Loader2, Plug, Plus, Trash2, Wifi } from "lucide-react";
import { toast } from "sonner";

const URI_PLACEHOLDER: Record<Engine, string> = {
  mongodb: "mongodb://host:27017",
  postgresql: "postgresql://user:password@host:5432",
};

function AddConnectionDialog() {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({
    name: "",
    engine: "mongodb" as Engine,
    uri: "",
    database: "",
  });

  const add = useMutation({
    mutationFn: () => addConnection(form),
    onSuccess: (conn) => {
      // The backend tests the connection before saving, so success here means
      // it's reachable. Invalidate the cached list so every page refreshes.
      queryClient.invalidateQueries({ queryKey: ["connections"] });
      toast.success(`Connected to ${conn.name}`);
      setOpen(false);
      setForm({ name: "", engine: "mongodb", uri: "", database: "" });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const valid = form.name && form.uri && form.database;

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger render={<Button className="gap-1.5" />}>
        <Plus className="size-4" /> Add connection
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add a database connection</DialogTitle>
          <DialogDescription>
            The connection is tested before it&apos;s saved — a failing URI is rejected.
          </DialogDescription>
        </DialogHeader>
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            if (valid) add.mutate();
          }}
        >
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="conn-name">Name</Label>
              <Input
                id="conn-name"
                placeholder="production-replica"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
              />
            </div>
            <div className="space-y-1.5">
              <Label>Engine</Label>
              <Select
                value={form.engine}
                onValueChange={(v) => v && setForm({ ...form, engine: v as Engine })}
              >
                <SelectTrigger className="w-full">
                  <SelectValue>
                    {form.engine === "mongodb" ? "MongoDB" : "PostgreSQL"}
                  </SelectValue>
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="mongodb">MongoDB</SelectItem>
                  <SelectItem value="postgresql">PostgreSQL</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="conn-uri">Connection URI</Label>
            <Input
              id="conn-uri"
              placeholder={URI_PLACEHOLDER[form.engine]}
              value={form.uri}
              onChange={(e) => setForm({ ...form, uri: e.target.value })}
              className="font-mono text-sm"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="conn-db">Database</Label>
            <Input
              id="conn-db"
              placeholder="my_database"
              value={form.database}
              onChange={(e) => setForm({ ...form, database: e.target.value })}
            />
          </div>
          <DialogFooter>
            <Button type="submit" disabled={!valid || add.isPending} className="gap-1.5">
              {add.isPending ? (
                <>
                  <Loader2 className="size-4 animate-spin" /> Testing connection…
                </>
              ) : (
                <>
                  <CheckCircle2 className="size-4" /> Test & save
                </>
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export default function ConnectionsPage() {
  const { connections, isLoading } = useConnection();
  const queryClient = useQueryClient();
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);

  const test = useMutation({
    mutationFn: testConnection,
    onSuccess: (r) =>
      r.ok ? toast.success(r.message) : toast.error(r.message),
    onError: (e: Error) => toast.error(e.message),
  });

  const remove = useMutation({
    mutationFn: deleteConnection,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["connections"] });
      toast.success("Connection removed");
      setConfirmDelete(null);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <div className="mx-auto max-w-4xl space-y-6 px-8 py-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Connections</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Databases QueryLens can query. Credentials are never returned by the API.
          </p>
        </div>
        <AddConnectionDialog />
      </div>

      <div className="space-y-3">
        {isLoading &&
          Array.from({ length: 2 }).map((_, i) => <Skeleton key={i} className="h-24" />)}

        {connections.map((c) => (
          <Card key={c.connection_id}>
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center gap-3 text-base">
                <Plug className="size-4 text-muted-foreground" />
                {c.name}
                <EngineBadge engine={c.engine} />
                <span className="ml-auto flex gap-1.5">
                  <Button
                    variant="outline"
                    size="sm"
                    className="gap-1.5"
                    disabled={test.isPending}
                    onClick={() => test.mutate(c.connection_id)}
                  >
                    {test.isPending && test.variables === c.connection_id ? (
                      <Loader2 className="size-3.5 animate-spin" />
                    ) : (
                      <Wifi className="size-3.5" />
                    )}
                    Test
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    className="gap-1.5 text-destructive hover:text-destructive"
                    onClick={() => setConfirmDelete(c.connection_id)}
                  >
                    <Trash2 className="size-3.5" /> Delete
                  </Button>
                </span>
              </CardTitle>
            </CardHeader>
            <CardContent className="flex gap-6 text-sm text-muted-foreground">
              <span className="font-mono text-xs">{c.uri_masked}</span>
              <span>
                db: <span className="font-mono text-xs">{c.database}</span>
              </span>
              {c.created_at && (
                <span className="ml-auto text-xs">
                  added {new Date(c.created_at).toLocaleDateString()}
                </span>
              )}
            </CardContent>
          </Card>
        ))}
      </div>

      <Dialog open={confirmDelete !== null} onOpenChange={(o) => !o && setConfirmDelete(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete this connection?</DialogTitle>
            <DialogDescription>
              QueryLens forgets the connection details. The database itself is not touched.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmDelete(null)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              disabled={remove.isPending}
              onClick={() => confirmDelete && remove.mutate(confirmDelete)}
            >
              {remove.isPending ? "Deleting…" : "Delete"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
