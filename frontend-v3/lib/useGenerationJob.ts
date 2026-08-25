"use client";

import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { getGenerationJob } from "@/lib/api";
import type { CvGenerationResult, GenerationJobOut } from "@/lib/types";

const POLL_INTERVAL_MS = 1500;

export function useGenerationJob<TResult = CvGenerationResult>(
  token: string | null,
  jobId: string | null
) {
  const query = useQuery<GenerationJobOut<TResult>>({
    queryKey: ["generation-job", jobId],
    queryFn: () => getGenerationJob<TResult>(token as string, jobId as string),
    enabled: !!token && !!jobId,
  });

  const status = query.data?.status;
  const { refetch } = query;

  // Manual polling rather than react-query's `refetchInterval` option: in
  // this app's dev environment the interval option reliably fired once and
  // then never rescheduled (observed via instrumented logging - the query
  // fetched, computed the next interval correctly, but no further fetch
  // ever followed). A plain setInterval driving explicit refetch() calls
  // sidesteps whatever internal scheduling issue that was and is easy to
  // reason about.
  useEffect(() => {
    if (!token || !jobId || status !== "running") return;
    const timer = setInterval(() => {
      refetch();
    }, POLL_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [token, jobId, status, refetch]);

  return {
    job: query.data ?? null,
    isPolling: query.isFetching || status === "running",
    error: query.error,
  };
}
