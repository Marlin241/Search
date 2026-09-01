"use client";

import { Sidebar } from "./Sidebar";
import { MobileNav } from "./MobileNav";
import { RequireAuth } from "./RequireAuth";
import { BetaBanner } from "@/components/common/BetaBanner";
import { FeedbackButton } from "@/components/feedback/FeedbackButton";

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <RequireAuth>
      <div className="flex h-screen w-screen flex-col overflow-hidden bg-background text-foreground">
        <BetaBanner />

        <div className="flex flex-1 overflow-hidden">
          {/* Desktop Sidebar */}
          <Sidebar />

          {/* Main Content Area */}
          <div className="flex flex-1 flex-col h-full min-w-0 overflow-hidden">
            <main className="flex-1 overflow-y-auto px-4 py-6 sm:px-8 sm:py-8 pb-24 lg:pb-8 w-full max-w-6xl mx-auto">
              {children}
            </main>
          </div>
        </div>

        {/* Mobile Navigation */}
        <MobileNav />
        <FeedbackButton />
      </div>
    </RequireAuth>
  );
}
