"use client";

import { useEffect, useRef, useState } from "react";
import { Loader2 } from "lucide-react";
import { renderCvPreview } from "@/lib/api";
import type { CvStyleOptions, CvTemplate, RewrittenCv } from "@/lib/types";

const DEBOUNCE_MS = 500;

export function CvPreviewFrame({
  token,
  savedJobId,
  content,
  template,
  style,
}: {
  token: string;
  savedJobId: number;
  content: RewrittenCv;
  template: CvTemplate;
  style: CvStyleOptions;
}) {
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const previewUrlRef = useRef<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    const timer = setTimeout(() => {
      renderCvPreview(token, savedJobId, { content, template, style })
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
  }, [token, savedJobId, JSON.stringify(content), template, JSON.stringify(style)]);

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
