"use client";

import { useCallback } from "react";
import { useParams } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { getDiagnostic, renderCvPreviewForDiagnostic } from "@/lib/api";
import { CvEditorShell } from "@/components/cv-editor/CvEditorShell";

export default function DiagnosticCvEditorPage() {
  const { token } = useAuth();
  const params = useParams<{ diagnosticId: string }>();
  const diagnosticId = Number(params.diagnosticId);

  const loadContent = useCallback(async () => {
    const report = await getDiagnostic(token as string, diagnosticId).catch((err) => {
      throw { detail: err?.detail || "Ce diagnostic n'existe pas ou plus." };
    });
    const cvDocument = report.documents.find((doc) => doc.kind === "cv");
    return cvDocument?.content_json ?? null;
  }, [token, diagnosticId]);

  const doRenderPreview = useCallback(
    (payload: Parameters<typeof renderCvPreviewForDiagnostic>[2]) =>
      renderCvPreviewForDiagnostic(token as string, diagnosticId, payload),
    [token, diagnosticId]
  );

  return (
    <CvEditorShell
      title="votre diagnostic"
      backHref="/diagnostic"
      backLabel="Retour au diagnostic"
      cacheKey={`diagnostic:${diagnosticId}`}
      loadContent={loadContent}
      renderPreview={doRenderPreview}
      emptyStateGoToCvHref="/diagnostic"
      notFoundTitle="Diagnostic introuvable"
      notFoundHref="/diagnostic"
      notFoundLabel="Retour au diagnostic"
    />
  );
}
