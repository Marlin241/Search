"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

// The flat candidatures list was retired in favor of the dashboard's
// Kanban board (Phase 7) - this route now just redirects, so any old
// link/bookmark still lands somewhere useful instead of a 404.
export default function CandidaturesRedirectPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/dashboard");
  }, [router]);

  return null;
}
