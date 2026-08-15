import type { BannerContent } from "@/lib/errors";

export function ErrorBanner({ content }: { content: BannerContent }) {
  const styles =
    content.variant === "warning" ? "bg-pending-soft text-pending-ink" : "bg-attention-soft text-attention-ink";
  return (
    <p role="alert" className={`rounded-2xl px-4 py-3 text-sm font-medium ${styles}`}>
      {content.message}
    </p>
  );
}
