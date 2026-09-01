import { Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";
import { PRODUCT_NAME } from "@/lib/brand";

export function Logo({
  className,
  wordmark = true,
}: {
  className?: string;
  wordmark?: boolean;
}) {
  return (
    <span className={cn("flex items-center gap-2.5", className)}>
      <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-tr from-primary-600 to-accent text-white shadow-soft">
        <Sparkles className="h-5 w-5" />
      </span>
      {wordmark && (
        <span className="font-display text-xl font-bold tracking-tight text-foreground">
          {PRODUCT_NAME}
        </span>
      )}
    </span>
  );
}
