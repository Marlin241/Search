"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";

export function TopNav() {
  const { user, logout } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  if (!user) {
    return (
      <header className="border-b border-slate-200 bg-white px-6 py-3">
        <span className="text-base font-bold text-slate-900">📄 Diagnostic ATS</span>
      </header>
    );
  }

  function handleLogout() {
    logout();
    router.replace("/login");
  }

  return (
    <header className="flex items-center justify-between border-b border-slate-200 bg-white px-6 py-3">
      <span className="text-base font-bold text-slate-900">📄 Diagnostic ATS</span>
      <nav className="flex items-center gap-5 text-sm text-slate-600">
        <Link href="/diagnostic" className={pathname === "/diagnostic" ? "font-semibold text-blue-600" : ""}>
          Nouveau diagnostic
        </Link>
        <Link href="/historique" className={pathname === "/historique" ? "font-semibold text-blue-600" : ""}>
          Historique
        </Link>
        <span>{user.email}</span>
        <button type="button" onClick={handleLogout} className="font-semibold text-slate-600">
          Se déconnecter
        </button>
      </nav>
    </header>
  );
}
