"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ConnectionSwitcher } from "@/components/connection-switcher";
import { cn } from "@/lib/utils";
import { LayoutDashboard, MessageSquare, Network, Plug, ScanSearch } from "lucide-react";

const NAV = [
  { href: "/", label: "Chat", icon: MessageSquare },
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/connections", label: "Connections", icon: Plug },
  { href: "/schema", label: "Schema", icon: Network },
];

export function AppSidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex h-screen w-60 shrink-0 flex-col border-r bg-sidebar">
      <div className="flex items-center gap-2 px-4 py-5">
        <div className="flex size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
          <ScanSearch className="size-4.5" />
        </div>
        <div>
          <div className="text-sm font-semibold leading-none">QueryLens</div>
          <div className="mt-1 text-[11px] text-muted-foreground">
            Chat with your database
          </div>
        </div>
      </div>

      <nav className="flex flex-col gap-1 px-3">
        {NAV.map(({ href, label, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            className={cn(
              "flex items-center gap-2.5 rounded-md px-3 py-2 text-sm transition-colors",
              pathname === href
                ? "bg-accent font-medium text-accent-foreground"
                : "text-muted-foreground hover:bg-accent/50 hover:text-foreground",
            )}
          >
            <Icon className="size-4" />
            {label}
          </Link>
        ))}
      </nav>

      <div className="mt-auto space-y-2 border-t p-3">
        <div className="px-1 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
          Active connection
        </div>
        <ConnectionSwitcher />
      </div>
    </aside>
  );
}
