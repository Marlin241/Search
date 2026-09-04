"use client";

import { useEffect, useRef, useState } from "react";
import { Loader2 } from "lucide-react";
import type { CvStyleOptions, CvTemplate, RewrittenCv } from "@/lib/types";

const DEBOUNCE_MS = 500;

export function CvPreviewFrame({
  cacheKey,
  renderPreview,
  content,
  template,
  style,
}: {
  /** Identifies the scope being previewed (e.g. `savedJob:${id}` or
   * `diagnostic:${id}`) so the debounce effect below only restarts when the
   * scope itself changes, not on every render. */
  cacheKey: string;
  renderPreview: (payload: {
    content: RewrittenCv;
    template: CvTemplate;
    style: CvStyleOptions;
  }) => Promise<Blob>;
  content: RewrittenCv;
  template: CvTemplate;
  style: CvStyleOptions;
}) {
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const previewUrlRef = useRef<string | null>(null);
  const renderPreviewRef = useRef(renderPreview);
  renderPreviewRef.current = renderPreview;

  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    const timer = setTimeout(() => {
      renderPreviewRef
        .current({ content, template, style })
        .then((blob) => {
          if (cancelled) return;
          const url = URL.createObjectURL(blob);
          if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current);
          previewUrlRef.current = url;
          setPreviewUrl(url);
        })
        .finally(() => {
          if (!cancelled) setIsLoading(false);
        });
    }, DEBOUNCE_MS);

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cacheKey, JSON.stringify(content), template, JSON.stringify(style)]);

  useEffect(() => {
    return () => {
      if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current);
    };
  }, []);

  return (
    <div className="relative w-full h-full rounded-xl overflow-hidden border border-border bg-muted/20">
      {isLoading && (
        <div className="absolute inset-0 flex items-center justify-center bg-card/60 z-10">
          <Loader2 className="w-5 h-5 animate-spin text-primary" />
        </div>
      )}
      {previewUrl && (
        <iframe src={previewUrl} className="w-full h-full" title="Aperçu CV" />
      )}
    </div>
  );
}
