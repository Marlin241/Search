"use client";

import { useState } from "react";
import { LayoutGrid, Users, Ticket, MessageSquare } from "lucide-react";
import { cn } from "@/lib/utils";
import { OverviewTab } from "@/components/admin/OverviewTab";
import { UsersTab } from "@/components/admin/UsersTab";
import { InvitesTab } from "@/components/admin/InvitesTab";
import { FeedbackTab } from "@/components/admin/FeedbackTab";

type Tab = "overview" | "users" | "invites" | "feedback";

const TABS: { id: Tab; label: string; icon: typeof Users }[] = [
  { id: "overview", label: "Vue d'ensemble", icon: LayoutGrid },
  { id: "users", label: "Utilisateurs", icon: Users },
  { id: "invites", label: "Invitations", icon: Ticket },
  { id: "feedback", label: "Feedback", icon: MessageSquare },
];

export default function AdminPage() {
  const [tab, setTab] = useState<Tab>("overview");

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <h1 className="font-display text-3xl font-bold text-foreground">Admin</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Suivi de la beta : inscrits, usage LLM, invitations, retours.
        </p>
      </div>

      <div className="flex items-center gap-1 overflow-x-auto border-b border-border">
        {TABS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            type="button"
            onClick={() => setTab(id)}
            className={cn(
              "flex items-center gap-1.5 whitespace-nowrap border-b-2 -mb-px px-4 py-2.5 text-xs font-semibold transition-colors",
              tab === id
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground"
            )}
          >
            <Icon className="h-3.5 w-3.5" />
            {label}
          </button>
        ))}
      </div>

      {tab === "overview" && <OverviewTab />}
      {tab === "users" && <UsersTab />}
      {tab === "invites" && <InvitesTab />}
      {tab === "feedback" && <FeedbackTab />}
    </div>
  );
}
