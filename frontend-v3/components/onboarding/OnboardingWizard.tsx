"use client";

import { useState } from "react";
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
import { StepJobTitles } from "./StepJobTitles";
import { StepLocationAndContract } from "./StepLocationAndContract";
import { StepGoalsAndCv } from "./StepGoalsAndCv";
import { StepPhotoPicker } from "./StepPhotoPicker";
import { StepConfirm } from "./StepConfirm";
import type { ExtractedPhotoOut } from "@/lib/types";

const TOTAL_STEPS = 5;

export function OnboardingWizard() {
  const router = useRouter();
  const { token, user } = useAuth();

  const [step, setStep] = useState(0);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Step 1
  const [desiredJobTitles, setDesiredJobTitles] = useState<string[]>([]);
  const [seniorityLevel, setSeniorityLevel] = useState<string | null>(null);

  // Step 2
  const [desiredLocations, setDesiredLocations] = useState<string[]>([]);
  const [remotePreference, setRemotePreference] = useState(false);
  const [contractTypes, setContractTypes] = useState<string[]>([]);
  const [salaryMin, setSalaryMin] = useState(25000);
  const [salaryMax, setSalaryMax] = useState(45000);

  // Step 3
  const [weeklyGoal, setWeeklyGoal] = useState(5);
  const [cvFile, setCvFile] = useState<File | null>(null);
  const [photoCandidates, setPhotoCandidates] = useState<ExtractedPhotoOut[]>([]);
  const [isExtractingPhotos, setIsExtractingPhotos] = useState(false);

  // Step 4
  const [selectedPhotoKey, setSelectedPhotoKey] = useState<string | null>(null);

  const canGoNext = (): boolean => {
    if (step === 0) return desiredJobTitles.length > 0 && !!seniorityLevel;
    if (step === 2) return cvFile !== null;
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
        desired_job_titles: desiredJobTitles,
        seniority_level: seniorityLevel,
        desired_locations: desiredLocations,
        remote_preference: remotePreference,
        contract_types: contractTypes,
        salary_min: salaryMin,
        salary_max: salaryMax,
        weekly_application_goal: weeklyGoal,
      });
      if (selectedPhotoKey !== null) {
        await setProfilePhoto(token, selectedPhotoKey);
      }
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
              <StepJobTitles
                desiredJobTitles={desiredJobTitles}
                onDesiredJobTitlesChange={setDesiredJobTitles}
                seniorityLevel={seniorityLevel}
                onSeniorityLevelChange={setSeniorityLevel}
              />
            )}
            {step === 1 && (
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
              />
            )}
            {step === 2 && (
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
            {step === 3 && (
              <StepPhotoPicker
                candidates={photoCandidates}
                isExtracting={isExtractingPhotos}
                selectedKey={selectedPhotoKey}
                onSelect={setSelectedPhotoKey}
                fullName={user?.email ?? ""}
                onManualUpload={handleManualPhotoUpload}
              />
            )}
            {step === 4 && (
              <StepConfirm
                desiredJobTitles={desiredJobTitles}
                desiredLocations={desiredLocations}
                remotePreference={remotePreference}
                contractTypes={contractTypes}
                salaryMin={salaryMin}
                salaryMax={salaryMax}
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
