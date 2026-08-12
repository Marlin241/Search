"use client";

import type { ReactNode } from "react";
import { Sidebar } from "./Sidebar";
import { useAuth } from "@/context/AuthContext";

export function AppShell({ children }: { children: ReactNode }) {
  const { user } = useAuth();

  if (!user) {
    return <>{children}</>;
  }

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  );
}
