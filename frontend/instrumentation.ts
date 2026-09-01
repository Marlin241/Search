import * as Sentry from "@sentry/nextjs";
import { scrubSentryEvent } from "@/lib/observability";

export async function register() {
  const dsn = process.env.NEXT_PUBLIC_GLITCHTIP_DSN;
  if (!dsn) return;
  if (
    process.env.NEXT_RUNTIME === "nodejs" ||
    process.env.NEXT_RUNTIME === "edge"
  ) {
    Sentry.init({
      dsn,
      environment: process.env.NODE_ENV,
      tracesSampleRate: 0,
      sendDefaultPii: false,
      maxBreadcrumbs: 20,
      beforeSend: scrubSentryEvent,
    });
  }
}

export const onRequestError = Sentry.captureRequestError;
