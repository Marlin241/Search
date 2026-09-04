"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LogOut, Moon, Sun } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { useTheme } from "@/context/ThemeContext";
import { cn, getInitials } from "@/lib/utils";
import { Logo } from "@/components/common/Logo";
import { ADMIN_NAV_ITEM, NAV_ITEMS, isNavItemActive } from "@/lib/navConfig";

export function Sidebar() {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();

  // "Mon profil" is reachable from the identity block below instead of as a
  // separate nav entry, to avoid showing it twice on desktop.
  const navItems = (user?.is_admin ? [...NAV_ITEMS, ADMIN_NAV_ITEM] : NAV_ITEMS).filter(
    (item) => item.href !== "/profil"
  );

  return (
    <aside className="hidden lg:flex h-full w-64 flex-col justify-between overflow-y-auto border-r border-border/80 bg-card/60 px-4 py-6 backdrop-blur-xl shrink-0">
      <div className="space-y-6">
        {/* Brand */}
        <Link href="/dashboard" className="flex px-3">
          <Logo />
        </Link>

        {/* Nav Links */}
        <nav className="space-y-1">
          {navItems.map((item) => {
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
      <div className="border-t border-border/60 pt-4 space-y-1">
        <Link
          href="/profil"
          className={cn(
            "flex items-center gap-3 rounded-lg px-2 py-2 -mx-2 transition-colors",
            pathname.startsWith("/profil")
              ? "bg-primary/10"
              : "hover:bg-muted/60"
          )}
        >
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/15 font-display text-xs font-bold text-primary">
            {user?.email ? getInitials(user.email) : "U"}
          </div>
          <div className="flex-1 min-w-0">
            <p className="truncate text-xs font-medium text-foreground">
              {user?.email}
            </p>
            <p className="text-[10px] text-muted-foreground">Voir mon profil</p>
          </div>
        </Link>

        <div className="flex items-center gap-1.5">
          <button
            onClick={logout}
            className="flex flex-1 items-center gap-2.5 rounded-lg px-3 py-2 text-xs font-medium text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
          >
            <LogOut className="h-4 w-4" />
            <span>Déconnexion</span>
          </button>

          <button
            onClick={toggleTheme}
            title={theme === "dark" ? "Passer au thème clair" : "Passer au thème sombre"}
            aria-label={theme === "dark" ? "Passer au thème clair" : "Passer au thème sombre"}
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted/60 hover:text-foreground"
          >
            {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </button>
        </div>
      </div>
    </aside>
  );
}
