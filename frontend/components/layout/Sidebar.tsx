"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LogOut, Sparkles } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { cn, getInitials } from "@/lib/utils";
import { ADMIN_NAV_ITEM, NAV_ITEMS, isNavItemActive } from "@/lib/navConfig";

export function Sidebar() {
  const pathname = usePathname();
  const { user, logout } = useAuth();

  return (
    <aside className="hidden lg:flex h-screen w-64 flex-col justify-between border-r border-border/80 bg-card/60 px-4 py-6 backdrop-blur-xl shrink-0">
      <div className="space-y-6">
        {/* Brand */}
        <Link href="/dashboard" className="flex items-center gap-2.5 px-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-tr from-primary-600 to-accent text-white shadow-soft">
            <Sparkles className="h-5 w-5" />
          </div>
          <div>
            <span className="font-display text-xl font-bold tracking-tight text-foreground">
              Search
            </span>
            <span className="ml-1.5 rounded-md bg-primary/10 px-1.5 py-0.5 text-[10px] font-bold text-primary">
              v3
            </span>
          </div>
        </Link>

        {/* Nav Links */}
        <nav className="space-y-1">
          {(user?.is_admin ? [...NAV_ITEMS, ADMIN_NAV_ITEM] : NAV_ITEMS).map((item) => {
            const isActive = isNavItemActive(pathname, item.href);
            const Icon = item.icon;

            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "group flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-all",
                  isActive
                    ? "bg-primary/10 text-primary font-semibold shadow-soft"
                    : "text-muted-foreground hover:bg-muted/60 hover:text-foreground"
                )}
              >
                <Icon
                  className={cn(
                    "h-4 w-4 transition-transform group-hover:scale-110",
                    isActive ? "text-primary" : "text-muted-foreground"
                  )}
                />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>
      </div>

      {/* User Section */}
      <div className="border-t border-border/60 pt-4 space-y-3">
        <div className="flex items-center gap-3 px-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/15 font-display text-xs font-bold text-primary">
            {user?.email ? getInitials(user.email) : "U"}
          </div>
          <div className="flex-1 min-w-0">
            <p className="truncate text-xs font-medium text-foreground">
              {user?.email}
            </p>
            <p className="text-[10px] text-muted-foreground">Compte connecté</p>
          </div>
        </div>

        <button
          onClick={logout}
          className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-xs font-medium text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
        >
          <LogOut className="h-4 w-4" />
          <span>Déconnexion</span>
        </button>
      </div>
    </aside>
  );
}
