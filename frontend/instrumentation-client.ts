import * as Sentry from "@sentry/nextjs";

const dsn = process.env.NEXT_PUBLIC_GLITCHTIP_DSN;

if (dsn) {
  try {
    Sentry.init({
      dsn,
      environment: process.env.NODE_ENV,
      tracesSampleRate: 0,
      sendDefaultPii: false,
      beforeBreadcrumb(crumb) {
        // Don't record request/response bodies in fetch/xhr breadcrumbs.
        if (crumb.category === "fetch" || crumb.category === "xhr") {
          const data = crumb.data as Record<string, unknown> | undefined;
          if (data) delete data["request_body"];
        }
        return crumb;
      },
    });
  } catch {
    /* never let error tracking break the app */
  }
}

export const onRouterTransitionStart = Sentry.captureRouterTransitionStart;
