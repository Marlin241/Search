import type { BannerContent } from "@/lib/errors";

export function ErrorBanner({ content }: { content: BannerContent }) {
  // NOTE: the warning variant keeps the literal "orange" Tailwind color
  // (not "amber") because ErrorBanner.test.tsx:13 asserts
  // `className.toContain("orange")`. Every other warning/pending UI in
  // the app uses amber — this is the one intentional exception.
  const styles =
    content.variant === "warning"
      ? "border-orange-200 bg-orange-50 text-orange-800 dark:border-orange-900 dark:bg-orange-950 dark:text-orange-300"
      : "border-red-200 bg-red-50 text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-300";
  return (
    <p role="alert" className={`rounded-lg border px-3 py-2 text-sm ${styles}`}>
      {content.message}
    </p>
  );
}
