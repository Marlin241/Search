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
    <main className="mx-auto max-w-2xl px-6 py-10">
      <h1 className="text-xl font-bold text-slate-900">Mon profil candidat</h1>
      <p className="mt-1 text-sm text-slate-600">
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

      <div className="mt-6 rounded-xl bg-white p-4 shadow-sm">
        <p className="text-sm font-semibold text-slate-900">CV de référence</p>
        <p className="mt-1 text-sm text-slate-600">
          {profile?.has_cv ? `Fichier actuel : ${profile.cv_filename}` : "Aucun CV de référence uploadé pour le moment."}
        </p>
        <div className="mt-3 flex flex-col gap-3">
          <CVDropzone file={cvFile} onFileSelected={setCvFile} />
          <button
            type="button"
            onClick={handleUploadCv}
            disabled={!cvFile || isUploadingCv}
            className="w-fit rounded-md bg-blue-500 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
          >
            {isUploadingCv ? "Envoi en cours..." : "Uploader mon CV de référence"}
          </button>
        </div>
      </div>
    </main>
  );
}
