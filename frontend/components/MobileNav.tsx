"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { FileSearch, Send, History, User } from "lucide-react";

const NAV_ITEMS = [
  { href: "/diagnostic", label: "Diagnostic", icon: FileSearch },
  { href: "/candidatures", label: "Candidatures", icon: Send },
  { href: "/historique", label: "Historique", icon: History },
  { href: "/profil", label: "Profil", icon: User },
] as const;

export function MobileNav() {
  const pathname = usePathname();

  return (
    <nav className="fixed inset-x-0 bottom-0 z-40 flex justify-around border-t border-border bg-surface px-1.5 pb-[max(8px,env(safe-area-inset-bottom))] pt-2 md:hidden">
      {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
        const isActive = pathname === href;
        return (
          <Link
            key={href}
            href={href}
            className={`flex flex-col items-center gap-[3px] rounded-2xl px-2.5 py-1.5 text-[11px] font-semibold ${
              isActive ? "text-accent-strong" : "text-ink-faint"
            }`}
          >
            <Icon className="h-[19px] w-[19px]" aria-hidden="true" />
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
