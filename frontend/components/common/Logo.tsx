import { cn } from "@/lib/utils";
import { PRODUCT_NAME } from "@/lib/brand";
import { LogoMark } from "@/components/common/LogoMark";

export function Logo({
  className,
  wordmark = true,
}: {
  className?: string;
  wordmark?: boolean;
}) {
  return (
    <span className={cn("flex items-center gap-2.5 text-foreground", className)}>
      <LogoMark className="h-8 w-8 shrink-0" />
      {wordmark && (
        <span className="font-display text-xl font-bold tracking-tight">
          {PRODUCT_NAME}
        </span>
      )}
    </span>
  );
}
