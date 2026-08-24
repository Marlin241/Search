import React from "react";
import { cn } from "@/lib/utils";

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "default" | "success" | "warning" | "destructive" | "accent" | "outline";
  size?: "sm" | "md";
}

export const Badge = React.forwardRef<HTMLDivElement, BadgeProps>(
  ({ className, variant = "default", size = "sm", ...props }, ref) => {
    const variants = {
      default: "bg-secondary text-secondary-foreground border border-border/50",
      success: "bg-success/15 text-success border border-success/30",
      warning: "bg-warning/15 text-warning-dark border border-warning/30",
      destructive: "bg-destructive/15 text-destructive border border-destructive/30",
      accent: "bg-accent/15 text-accent-foreground border border-accent/30",
      outline: "text-foreground border border-border bg-transparent",
    };

    const sizes = {
      sm: "px-2 py-0.5 text-xs font-medium",
      md: "px-2.5 py-1 text-sm font-medium",
    };

    return (
      <div
        ref={ref}
        className={cn(
          "inline-flex items-center rounded-full transition-colors",
          variants[variant],
          sizes[size],
          className
        )}
        {...props}
      />
    );
  }
);
Badge.displayName = "Badge";
