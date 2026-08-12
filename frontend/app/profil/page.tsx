"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { RequireAuth } from "@/components/RequireAuth";
import { CVDropzone } from "@/components/CVDropzone";
import { ErrorBanner } from "@/components/ErrorBanner";
import {
  CandidateProfileForm,
  EMPTY_CANDIDATE_PROFILE_FORM_VALUE,
  toCandidateProfileInput,
  type CandidateProfileFormValue,
} from "@/components/CandidateProfileForm";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { toBannerContent, isSessionExpired, type BannerContent } from "@/lib/errors";
import { getCandidateProfile, updateCandidateProfile, uploadReferenceCv, ApiError } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import type { CandidateProfile } from "@/lib/types";

export default function ProfilPage() {
  return (
    <RequireAuth>
      <ProfilPageContent />
    </RequireAuth>
  );
}

function ProfilPageContent() {
  const { token, logout } = useAuth();
  const router = useRouter();
  const [formValue, setFormValue] = useState<CandidateProfileFormValue>(EMPTY_CANDIDATE_PROFILE_FORM_VALUE);
  const [profile, setProfile] = useState<CandidateProfile | null>(null);
  const [cvFile, setCvFile] = useState<File | null>(null);
  const [banner, setBanner] = useState<BannerContent | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [isUploadingCv, setIsUploadingCv] = useState(false);

  function handleAuthError(error: unknown): boolean {
    if (isSessionExpired(error)) {
      logout();
      router.replace("/login");
      return true;
    }
    return false;
  }

  useEffect(() => {
    if (!token) return;
    getCandidateProfile(token)
      .then((fetched) => {
        setProfile(fetched);
        setFormValue({
          full_name: fetched.full_name,
          phone: fetched.phone,
          address: fetched.address ?? "",
          linkedin_url: fetched.linkedin_url ?? "",
          portfolio_url: fetched.portfolio_url ?? "",
          work_authorization: fetched.work_authorization,
          salary_expectation: fetched.salary_expectation ?? "",
        });
      })
      .catch((error) => {
        // 404 just means "no profile saved yet" — not an error to surface.
        if (error instanceof ApiError && error.status === 404) return;
        if (!handleAuthError(error)) setBanner(toBannerContent(error));
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  async function handleSave() {
    if (!token) return;
    setBanner(null);
    setIsSaving(true);
    try {
      const updated = await updateCandidateProfile(token, toCandidateProfileInput(formValue));
      setProfile(updated);
    } catch (error) {
      if (!handleAuthError(error)) setBanner(toBannerContent(error));
    } finally {
      setIsSaving(false);
    }
  }

  async function handleUploadCv() {
    if (!token || !cvFile) return;
    setBanner(null);
    setIsUploadingCv(true);
    try {
      const updated = await uploadReferenceCv(token, cvFile);
      setProfile(updated);
      setCvFile(null);
    } catch (error) {
      if (!handleAuthError(error)) setBanner(toBannerContent(error));
    } finally {
      setIsUploadingCv(false);
    }
  }

  return (
    <main className="mx-auto max-w-2xl px-8 py-10">
      <p className="text-xs font-bold uppercase tracking-wide text-amber-600 dark:text-amber-400">Profil</p>
      <h1 className="mt-1 text-2xl font-extrabold tracking-tight text-slate-900 dark:text-slate-50">
        Mon profil candidat
      </h1>
      <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
        Ces informations servent à pré-remplir vos candidatures automatiques.
      </p>

      {banner && (
        <div className="mt-4">
          <ErrorBanner content={banner} />
        </div>
      )}

      <div className="mt-6">
        <CandidateProfileForm value={formValue} onChange={setFormValue} onSubmit={handleSave} isSubmitting={isSaving} />
      </div>

      <Card className="mt-6 p-4">
        <p className="text-sm font-semibold text-slate-900 dark:text-slate-50">CV de référence</p>
        <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
          {profile?.has_cv ? `Fichier actuel : ${profile.cv_filename}` : "Aucun CV de référence uploadé pour le moment."}
        </p>
        <div className="mt-3 flex flex-col gap-3">
          <CVDropzone file={cvFile} onFileSelected={setCvFile} />
          <Button onClick={handleUploadCv} disabled={!cvFile} isLoading={isUploadingCv} className="w-fit">
            {isUploadingCv ? "Envoi en cours..." : "Uploader mon CV de référence"}
          </Button>
        </div>
      </Card>
    </main>
  );
}
