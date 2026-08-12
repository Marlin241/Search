"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { FileSearch, Send, History, User, LogOut, FileText } from "lucide-react";
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
    <aside className="flex w-56 flex-shrink-0 flex-col border-r border-slate-200 bg-white px-3 py-4 dark:border-ink-800 dark:bg-ink-900">
      <Link
        href="/"
        className="mb-6 flex items-center gap-2 px-2 text-sm font-extrabold tracking-tight text-slate-900 dark:text-slate-50"
      >
        <FileText className="h-5 w-5 text-amber-600 dark:text-amber-400" aria-hidden="true" />
        Diagnostic ATS
      </Link>

      {user && (
        <>
          <nav className="flex flex-col gap-1">
            {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
              const isActive = pathname === href;
              return (
                <Link
                  key={href}
                  href={href}
                  className={`flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm font-semibold transition-colors ${
                    isActive
                      ? "bg-slate-900 text-white dark:bg-slate-50 dark:text-slate-900"
                      : "text-slate-600 hover:bg-slate-50 dark:text-slate-400 dark:hover:bg-ink-800"
                  }`}
                >
                  <Icon className="h-4 w-4" aria-hidden="true" />
                  {label}
                </Link>
              );
            })}
          </nav>

          <div className="mt-auto flex flex-col gap-2 border-t border-slate-200 pt-3 text-xs dark:border-ink-800">
            <span className="truncate px-2.5 text-slate-500 dark:text-slate-400">{user.email}</span>
            <button
              type="button"
              onClick={handleLogout}
              className="flex items-center gap-2 rounded-lg px-2.5 py-2 text-left text-sm font-semibold text-slate-600 hover:bg-slate-50 dark:text-slate-400 dark:hover:bg-ink-800"
            >
              <LogOut className="h-4 w-4" aria-hidden="true" />
              Se déconnecter
            </button>
          </div>
        </>
      )}
    </aside>
  );
}
