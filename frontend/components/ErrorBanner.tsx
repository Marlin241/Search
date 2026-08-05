import type { BannerContent } from "@/lib/errors";

export function ErrorBanner({ content }: { content: BannerContent }) {
  const styles =
    content.variant === "warning"
      ? "bg-orange-50 text-orange-800 border-orange-200"
      : "bg-red-50 text-red-700 border-red-200";
  return (
    <p role="alert" className={`rounded-md border px-3 py-2 text-sm ${styles}`}>
      {content.message}
    </p>
  );
}
