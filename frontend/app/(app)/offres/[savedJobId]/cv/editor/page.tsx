"use client";

import { useCallback, useState } from "react";
import { useParams } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { getSavedJob, renderCvPreview } from "@/lib/api";
import { CvEditorShell } from "@/components/cv-editor/CvEditorShell";

export default function CvEditorPage() {
  const { token } = useAuth();
  const params = useParams<{ savedJobId: string }>();
  const savedJobId = Number(params.savedJobId);
  const [title, setTitle] = useState(`Offre #${savedJobId}`);

  const loadContent = useCallback(async () => {
    const job = await getSavedJob(token as string, savedJobId).catch((err) => {
      throw { detail: err?.detail || "Cette offre sauvegardée n'existe pas ou plus." };
    });
    setTitle(job.title);
    const cvDocument = job.documents.find((doc) => doc.kind === "cv");
    return cvDocument?.content_json ?? null;
  }, [token, savedJobId]);

  const doRenderPreview = useCallback(
    (payload: Parameters<typeof renderCvPreview>[2]) =>
      renderCvPreview(token as string, savedJobId, payload),
    [token, savedJobId]
  );

  return (
    <CvEditorShell
      title={title}
      backHref={`/offres/${savedJobId}?tab=cv`}
      backLabel="Retour à l'offre"
      cacheKey={`saved-job:${savedJobId}`}
      loadContent={loadContent}
      renderPreview={doRenderPreview}
      emptyStateGoToCvHref={`/offres/${savedJobId}?tab=cv`}
      notFoundTitle="Offre introuvable"
      notFoundHref="/offres"
      notFoundLabel="Retour aux offres"
    />
  );
}
