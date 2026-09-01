import * as Sentry from "@sentry/nextjs";
import { scrubSentryEvent } from "@/lib/observability";

const dsn = process.env.NEXT_PUBLIC_GLITCHTIP_DSN;

if (dsn) {
  try {
    Sentry.init({
      dsn,
      environment: process.env.NODE_ENV,
      tracesSampleRate: 0,
      sendDefaultPii: false,
      maxBreadcrumbs: 20,
      beforeSend: scrubSentryEvent,
      beforeBreadcrumb(crumb) {
        // Never keep request/response bodies from fetch/xhr breadcrumbs, and
        // redact the reset-password token if it appears in a breadcrumb URL.
        if (crumb.category === "fetch" || crumb.category === "xhr") {
          const data = crumb.data as Record<string, unknown> | undefined;
          if (data) {
            delete data["request_body"];
            delete data["response_body"];
            if (typeof data["url"] === "string") {
              data["url"] = (data["url"] as string).replace(
                /token=[^&\s]+/gi,
                "token=[redacted]"
              );
            }
          }
        }
        return crumb;
      },
    });
  } catch {
    /* never let error tracking break the app */
  }
}

export const onRouterTransitionStart = Sentry.captureRouterTransitionStart;
