"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { ArrowLeft, ArrowRight, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "@/context/AuthContext";
import {
  extractCvPhotos,
  setProfilePhoto,
  submitOnboarding,
  uploadManualPhoto,
  uploadReferenceCv,
} from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { ProgressDots } from "./ProgressDots";
import { StepName } from "./StepName";
import { StepJobTitles } from "./StepJobTitles";
import { StepLocationAndContract } from "./StepLocationAndContract";
import { StepGoalsAndCv } from "./StepGoalsAndCv";
import { StepPhotoPicker } from "./StepPhotoPicker";
import { StepConfirm } from "./StepConfirm";
import type { ExtractedPhotoOut } from "@/lib/types";
import { DEFAULT_CURRENCY } from "@/lib/currencies";

const TOTAL_STEPS = 6;

// Brouillon best-effort en localStorage : ne couvre que les champs
// texte/liste (pas le fichier CV, non sérialisable) mais évite déjà de
// perdre toute la saisie identité/préférences sur un F5 accidentel.
const DRAFT_KEY = "search_onboarding_draft";

interface OnboardingDraft {
  firstName?: string;
  lastName?: string;
  desiredJobTitles?: string[];
  seniorityLevel?: string | null;
  desiredLocations?: string[];
  remotePreference?: boolean;
  contractTypes?: string[];
  salaryMin?: number;
  salaryMax?: number;
  salaryCurrency?: string;
  weeklyGoal?: number;
}

export function OnboardingWizard() {
  const router = useRouter();
  const { token, refreshProfile } = useAuth();

  const [step, setStep] = useState(0);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Step 0
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");

  // Step 1
  const [desiredJobTitles, setDesiredJobTitles] = useState<string[]>([]);
  const [seniorityLevel, setSeniorityLevel] = useState<string | null>(null);

  // Step 2
  const [desiredLocations, setDesiredLocations] = useState<string[]>([]);
  const [remotePreference, setRemotePreference] = useState(false);
  const [contractTypes, setContractTypes] = useState<string[]>([]);
  const [salaryMin, setSalaryMin] = useState(150000);
  const [salaryMax, setSalaryMax] = useState(350000);
  const [salaryCurrency, setSalaryCurrency] = useState(DEFAULT_CURRENCY);

  // Step 3
  const [weeklyGoal, setWeeklyGoal] = useState(5);
  const [cvFile, setCvFile] = useState<File | null>(null);
  const [photoCandidates, setPhotoCandidates] = useState<ExtractedPhotoOut[]>([]);
  const [isExtractingPhotos, setIsExtractingPhotos] = useState(false);

  // Step 4
  const [selectedPhotoKey, setSelectedPhotoKey] = useState<string | null>(null);

  // Restaure un brouillon existant une fois au montage (jamais sur le
  // serveur : localStorage n'existe pas là-bas, d'où l'effet plutôt qu'un
  // état initial paresseux).
  useEffect(() => {
    try {
      const raw = localStorage.getItem(DRAFT_KEY);
      if (!raw) return;
      const draft: OnboardingDraft = JSON.parse(raw);
      if (draft.firstName) setFirstName(draft.firstName);
      if (draft.lastName) setLastName(draft.lastName);
      if (draft.desiredJobTitles?.length) setDesiredJobTitles(draft.desiredJobTitles);
      if (draft.seniorityLevel) setSeniorityLevel(draft.seniorityLevel);
      if (draft.desiredLocations?.length) setDesiredLocations(draft.desiredLocations);
      if (typeof draft.remotePreference === "boolean")
        setRemotePreference(draft.remotePreference);
      if (draft.contractTypes?.length) setContractTypes(draft.contractTypes);
      if (typeof draft.salaryMin === "number") setSalaryMin(draft.salaryMin);
      if (typeof draft.salaryMax === "number") setSalaryMax(draft.salaryMax);
      if (draft.salaryCurrency) setSalaryCurrency(draft.salaryCurrency);
      if (typeof draft.weeklyGoal === "number") setWeeklyGoal(draft.weeklyGoal);
    } catch {
      // brouillon corrompu/illisible : on repart simplement à vide.
    }
  }, []);

  // Sauvegarde best-effort à chaque changement (pas le fichier CV, non
  // sérialisable en JSON).
  useEffect(() => {
    const draft: OnboardingDraft = {
      firstName,
      lastName,
      desiredJobTitles,
      seniorityLevel,
      desiredLocations,
      remotePreference,
      contractTypes,
      salaryMin,
      salaryMax,
      salaryCurrency,
      weeklyGoal,
    };
    try {
      localStorage.setItem(DRAFT_KEY, JSON.stringify(draft));
    } catch {
      // stockage indisponible (navigation privée, quota...) : tant pis.
    }
  }, [
    firstName,
    lastName,
    desiredJobTitles,
    seniorityLevel,
    desiredLocations,
    remotePreference,
    contractTypes,
    salaryMin,
    salaryMax,
    salaryCurrency,
    weeklyGoal,
  ]);

  const canGoNext = (): boolean => {
    if (step === 0) return firstName.trim().length > 0 && lastName.trim().length > 0;
    if (step === 1) return desiredJobTitles.length > 0 && !!seniorityLevel;
    if (step === 3) return cvFile !== null;
    return true;
  };

  const handleCvFileSelected = async (file: File) => {
    setCvFile(file);
    if (!token) return;

    try {
      await uploadReferenceCv(token, file);
    } catch (err: any) {
      toast.error(err?.detail || "Échec de l'import du CV.");
      setCvFile(null);
      return;
    }

    setIsExtractingPhotos(true);
    try {
      const candidates = await extractCvPhotos(token, file);
      setPhotoCandidates(candidates);
    } catch {
      setPhotoCandidates([]);
    } finally {
      setIsExtractingPhotos(false);
    }
  };

  const handleManualPhotoUpload = async (file: File) => {
    if (!token) return;
    try {
      const uploaded = await uploadManualPhoto(token, file);
      setPhotoCandidates((prev) => [...prev, uploaded]);
      setSelectedPhotoKey(uploaded.key);
    } catch (err: any) {
      toast.error(err?.detail || "Échec de l'import de l'image.");
    }
  };

  const handleNext = () => {
    if (step < TOTAL_STEPS - 1) setStep((s) => s + 1);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const handleBack = () => {
    if (step > 0) setStep((s) => s - 1);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const handleFinish = async () => {
    if (!token) return;
    setIsSubmitting(true);
    try {
      await submitOnboarding(token, {
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        desired_job_titles: desiredJobTitles,
        seniority_level: seniorityLevel,
        desired_locations: desiredLocations,
        remote_preference: remotePreference,
        contract_types: contractTypes,
        salary_min: salaryMin,
        salary_max: salaryMax,
        salary_currency: salaryCurrency,
        weekly_application_goal: weeklyGoal,
      });
      if (selectedPhotoKey !== null) {
        await setProfilePhoto(token, selectedPhotoKey);
      }
      try {
        localStorage.removeItem(DRAFT_KEY);
      } catch {
        // best-effort
      }
      await refreshProfile();
      toast.success("Ton profil est prêt !");
      router.push("/dashboard");
    } catch (err: any) {
      toast.error(err?.detail || "Une erreur est survenue.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="w-full max-w-xl">
      <div className="mb-8">
        <ProgressDots total={TOTAL_STEPS} current={step} />
      </div>

      <div className="rounded-3xl bg-card p-6 shadow-lift sm:p-8">
        <AnimatePresence mode="wait">
          <motion.div
            key={step}
            initial={{ opacity: 0, x: 16 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -16 }}
            transition={{ duration: 0.2 }}
          >
            {step === 0 && (
              <StepName
                firstName={firstName}
                onFirstNameChange={setFirstName}
                lastName={lastName}
                onLastNameChange={setLastName}
              />
            )}
            {step === 1 && (
              <StepJobTitles
                desiredJobTitles={desiredJobTitles}
                onDesiredJobTitlesChange={setDesiredJobTitles}
                seniorityLevel={seniorityLevel}
                onSeniorityLevelChange={setSeniorityLevel}
              />
            )}
            {step === 2 && (
              <StepLocationAndContract
                desiredLocations={desiredLocations}
                onDesiredLocationsChange={setDesiredLocations}
                remotePreference={remotePreference}
                onRemotePreferenceChange={setRemotePreference}
                contractTypes={contractTypes}
                onContractTypesChange={setContractTypes}
                salaryMin={salaryMin}
                salaryMax={salaryMax}
                onSalaryChange={(min, max) => {
                  setSalaryMin(min);
                  setSalaryMax(max);
                }}
                salaryCurrency={salaryCurrency}
                onSalaryCurrencyChange={setSalaryCurrency}
              />
            )}
            {step === 3 && (
              <StepGoalsAndCv
                weeklyGoal={weeklyGoal}
                onWeeklyGoalChange={setWeeklyGoal}
                cvFile={cvFile}
                onCvFileSelected={handleCvFileSelected}
                onCvFileCleared={() => {
                  setCvFile(null);
                  setPhotoCandidates([]);
                  setSelectedPhotoKey(null);
                }}
              />
            )}
            {step === 4 && (
              <StepPhotoPicker
                candidates={photoCandidates}
                isExtracting={isExtractingPhotos}
                selectedKey={selectedPhotoKey}
                onSelect={setSelectedPhotoKey}
                fullName={`${firstName} ${lastName}`.trim()}
                onManualUpload={handleManualPhotoUpload}
              />
            )}
            {step === 5 && (
              <StepConfirm
                firstName={firstName}
                lastName={lastName}
                desiredJobTitles={desiredJobTitles}
                desiredLocations={desiredLocations}
                remotePreference={remotePreference}
                contractTypes={contractTypes}
                salaryMin={salaryMin}
                salaryMax={salaryMax}
                salaryCurrency={salaryCurrency}
                weeklyGoal={weeklyGoal}
                cvFileName={cvFile?.name ?? null}
              />
            )}
          </motion.div>
        </AnimatePresence>

        <div className="mt-8 flex items-center justify-between">
          <Button
            type="button"
            variant="ghost"
            onClick={handleBack}
            className={step === 0 ? "invisible" : ""}
            icon={<ArrowLeft className="h-4 w-4" />}
          >
            Retour
          </Button>

          {step < TOTAL_STEPS - 1 ? (
            <Button
              type="button"
              variant="primary"
              onClick={handleNext}
              disabled={!canGoNext()}
              icon={<ArrowRight className="h-4 w-4" />}
            >
              Continuer
            </Button>
          ) : (
            <Button
              type="button"
              variant="primary"
              onClick={handleFinish}
              isLoading={isSubmitting}
              icon={
                isSubmitting ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <ArrowRight className="h-4 w-4" />
                )
              }
            >
              Terminer
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
