/**
 * Shared Sentry/GlitchTip event scrubber for both the client and server
 * instrumentation files, so error telemetry never carries request bodies,
 * cookies, or the password-reset token in a URL. Mirrors the backend's
 * app/observability._before_send.
 */
function redactTokenInUrl(value: string): string {
  return value.replace(/token=[^&\s]+/gi, "token=[redacted]");
}

// `event` is a Sentry Event; typed loosely to avoid coupling to the SDK's
// internal types (kept identical on client and server).
export function scrubSentryEvent<T extends Record<string, any>>(
  event: T
): T | null {
  const request = event.request as Record<string, any> | undefined;
  if (request) {
    delete request.data;
    delete request.cookies;
    if (typeof request.url === "string") {
      request.url = redactTokenInUrl(request.url);
    }
    if (typeof request.query_string === "string") {
      request.query_string = redactTokenInUrl(request.query_string);
    }
    if (request.headers && typeof request.headers === "object") {
      delete request.headers["Authorization"];
      delete request.headers["authorization"];
      delete request.headers["Cookie"];
      delete request.headers["cookie"];
    }
  }
  return event;
}
