"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { FileSearch, Send, History, User, LogOut } from "lucide-react";
import { useAuth } from "@/context/AuthContext";

const NAV_ITEMS = [
  { href: "/diagnostic", label: "Diagnostic", icon: FileSearch },
  { href: "/candidatures", label: "Candidatures", icon: Send },
  { href: "/historique", label: "Historique", icon: History },
  { href: "/profil", label: "Profil", icon: User },
] as const;

export function Sidebar() {
  const { user, logout } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  function handleLogout() {
    logout();
    router.replace("/login");
  }

  return (
    <aside className="hidden w-[236px] flex-shrink-0 flex-col border-r border-border bg-surface px-3.5 py-5 md:flex">
      <Link href="/" className="mb-6 flex items-center gap-2.5 px-1.5">
        <span className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-[11px] bg-gradient-to-br from-accent to-accent2 font-display text-sm font-extrabold text-ink-on-accent">
          D
        </span>
        <span className="font-display text-[15px] font-bold text-ink">Diagnostic ATS</span>
      </Link>

      {user && (
        <>
          <nav className="flex flex-col gap-[3px]">
            {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
              const isActive = pathname === href;
              return (
                <Link
                  key={href}
                  href={href}
                  className={`flex items-center gap-[11px] rounded-2xl px-3 py-2.5 text-sm font-semibold transition-colors ${
                    isActive ? "bg-accent text-ink-on-accent shadow-soft" : "text-ink-soft hover:bg-surface-2"
                  }`}
                >
                  <Icon className="h-[17px] w-[17px]" aria-hidden="true" />
                  {label}
                </Link>
              );
            })}
          </nav>

          <div className="mt-auto flex flex-col gap-1 border-t border-border pt-3.5 text-xs">
            <span className="truncate px-3 text-ink-faint">{user.email}</span>
            <button
              type="button"
              onClick={handleLogout}
              className="flex items-center gap-[11px] rounded-2xl px-3 py-2.5 text-left text-sm font-semibold text-ink-soft hover:bg-surface-2"
            >
              <LogOut className="h-[17px] w-[17px]" aria-hidden="true" />
              Se déconnecter
            </button>
          </div>
        </>
      )}
    </aside>
  );
}
