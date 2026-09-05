"use client";

import { useEffect, useState, useRef } from "react";
import {
  UserCheck,
  UploadCloud,
  FileCheck2,
  CheckCircle2,
  AlertCircle,
  Save,
  Trash2,
  Linkedin,
  Globe,
  Phone,
  MapPin,
  Banknote,
  Moon,
  Sun,
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { useTheme } from "@/context/ThemeContext";
import {
  getCandidateProfile,
  updateCandidateProfile,
  uploadReferenceCv,
  deleteProfile,
  submitOnboarding,
} from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Card, CardContent } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { Dialog } from "@/components/ui/Dialog";
import { StepJobTitles } from "@/components/onboarding/StepJobTitles";
import { StepLocationAndContract } from "@/components/onboarding/StepLocationAndContract";
import { UsageGauges } from "@/components/account/UsageGauges";
import { DangerZone } from "@/components/account/DangerZone";
import {
  cn,
  formatDate,
  isValidCvFile,
  MAX_FILE_SIZE,
} from "@/lib/utils";
import type { CandidateProfileOut } from "@/lib/types";
import { DEFAULT_CURRENCY } from "@/lib/currencies";

const WORK_AUTHORIZATIONS = [
  { value: "french_citizen", label: "Nationalité française / Citoyen UE" },
  { value: "visa_required", label: "Visa de travail requis" },
  { value: "work_permit", label: "Titre de séjour / Autorisation valide" },
];

export default function ProfilPage() {
  const { token, user } = useAuth();
  const { theme, toggleTheme } = useTheme();

  const [profile, setProfile] = useState<CandidateProfileOut | null>(null);
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [phone, setPhone] = useState("");
  const [address, setAddress] = useState("");
  const [linkedinUrl, setLinkedinUrl] = useState("");
  const [portfolioUrl, setPortfolioUrl] = useState("");
  const [workAuth, setWorkAuth] = useState("french_citizen");
  const [salaryExpectation, setSalaryExpectation] = useState("");

  // Préférences de recherche (collectées à l'onboarding, éditables ici aussi)
  const [desiredJobTitles, setDesiredJobTitles] = useState<string[]>([]);
  const [seniorityLevel, setSeniorityLevel] = useState<string | null>(null);
  const [desiredLocations, setDesiredLocations] = useState<string[]>([]);
  const [remotePreference, setRemotePreference] = useState(false);
  const [contractTypes, setContractTypes] = useState<string[]>([]);
  const [salaryMin, setSalaryMin] = useState(25000);
  const [salaryMax, setSalaryMax] = useState(45000);
  const [salaryCurrency, setSalaryCurrency] = useState(DEFAULT_CURRENCY);
  const [weeklyGoal, setWeeklyGoal] = useState(5);
  const [isSavingPrefs, setIsSavingPrefs] = useState(false);

  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isUploadingCv, setIsUploadingCv] = useState(false);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Delete modal
  const [isDeleteOpen, setIsDeleteOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const fileInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (!token) return;
    setIsLoading(true);
    getCandidateProfile(token)
      .then((res) => {
        setProfile(res);
        setFirstName(res.first_name || "");
        setLastName(res.last_name || "");
        setPhone(res.phone || "");
        setAddress(res.address || "");
        setLinkedinUrl(res.linkedin_url || "");
        setPortfolioUrl(res.portfolio_url || "");
        setWorkAuth(res.work_authorization || "french_citizen");
        setSalaryExpectation(res.salary_expectation || "");
        setDesiredJobTitles(res.desired_job_titles || []);
        setSeniorityLevel(res.seniority_level);
        setDesiredLocations(res.desired_locations || []);
        setRemotePreference(res.remote_preference);
        setContractTypes(res.contract_types || []);
        if (res.salary_min !== null) setSalaryMin(res.salary_min);
        if (res.salary_max !== null) setSalaryMax(res.salary_max);
        if (res.salary_currency) setSalaryCurrency(res.salary_currency);
        if (res.weekly_application_goal !== null) {
          setWeeklyGoal(res.weekly_application_goal);
        }
      })
      .catch((err) => console.log("Profile not yet created or empty"))
      .finally(() => setIsLoading(false));
  }, [token]);

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token) return;

    setIsSaving(true);
    setErrorMsg(null);
    setSuccessMsg(null);

    try {
      const updated = await updateCandidateProfile(token, {
        first_name: firstName,
        last_name: lastName,
        phone,
        address: address || null,
        linkedin_url: linkedinUrl || null,
        portfolio_url: portfolioUrl || null,
        work_authorization: workAuth,
        salary_expectation: salaryExpectation || null,
      });
      setProfile(updated);
      setSuccessMsg("Votre profil candidat a été mis à jour avec succès.");
      setTimeout(() => setSuccessMsg(null), 4000);
    } catch (err: any) {
      setErrorMsg(err?.detail || "Erreur lors de la mise à jour du profil.");
    } finally {
      setIsSaving(false);
    }
  };

  const handleSavePreferences = async () => {
    if (!token) return;

    setIsSavingPrefs(true);
    setErrorMsg(null);
    setSuccessMsg(null);

    try {
      const updated = await submitOnboarding(token, {
        first_name: firstName,
        last_name: lastName,
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
      setProfile(updated);
      setSuccessMsg("Vos préférences de recherche ont été mises à jour.");
      setTimeout(() => setSuccessMsg(null), 4000);
    } catch (err: any) {
      setErrorMsg(err?.detail || "Erreur lors de la mise à jour des préférences.");
    } finally {
      setIsSavingPrefs(false);
    }
  };

  const handleCvUpload = async (file: File) => {
    if (!token) return;
    if (!isValidCvFile(file)) {
      setErrorMsg("Format de fichier non valide (PDF ou DOCX uniquement).");
      return;
    }
    if (file.size > MAX_FILE_SIZE) {
      setErrorMsg("Le fichier dépasse la limite autorisée de 5 Mo.");
      return;
    }

    setIsUploadingCv(true);
    setErrorMsg(null);
    try {
      const updated = await uploadReferenceCv(token, file);
      setProfile(updated);
      setSuccessMsg("Votre CV de référence a été importé et analysé.");
      setTimeout(() => setSuccessMsg(null), 4000);
    } catch (err: any) {
      setErrorMsg(err?.detail || "Erreur lors de l'upload du CV.");
    } finally {
      setIsUploadingCv(false);
    }
  };

  const handleDeleteProfile = async () => {
    if (!token) return;
    setIsDeleting(true);
    try {
      await deleteProfile(token);
      setProfile(null);
      setFirstName("");
      setLastName("");
      setPhone("");
      setAddress("");
      setLinkedinUrl("");
      setPortfolioUrl("");
      setDesiredJobTitles([]);
      setSeniorityLevel(null);
      setDesiredLocations([]);
      setRemotePreference(false);
      setContractTypes([]);
      setSalaryMin(25000);
      setSalaryMax(45000);
      setSalaryCurrency(DEFAULT_CURRENCY);
      setWeeklyGoal(5);
      setIsDeleteOpen(false);
      setSuccessMsg("Vos données de profil ont été supprimées.");
    } catch (err) {
      console.error("Failed to delete profile:", err);
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <div className="space-y-8 animate-fade-in pb-20 max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-display font-bold text-foreground">
            Mon profil candidat
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Ces informations permettent de personnaliser vos candidatures et de pré-remplir les formulaires ATS.
          </p>
        </div>

        {profile && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setIsDeleteOpen(true)}
            icon={<Trash2 className="w-4 h-4 text-destructive" />}
            className="text-xs text-destructive hover:bg-destructive/10"
          >
            Effacer mon profil
          </Button>
        )}
      </div>

      {/* Notifications */}
      {successMsg && (
        <div className="p-3 bg-success/15 border border-success/30 text-success text-xs font-semibold rounded-xl flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 shrink-0" />
          <span>{successMsg}</span>
        </div>
      )}

      {errorMsg && (
        <div className="p-3 bg-destructive/10 border border-destructive/20 text-destructive text-xs font-semibold rounded-xl flex items-center gap-2">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* Appearance */}
      <Card>
        <CardContent className="p-6 flex items-center justify-between gap-4">
          <div>
            <h3 className="text-base font-bold font-display text-foreground">
              Apparence
            </h3>
            <p className="text-xs text-muted-foreground mt-1">
              Basculez entre le thème clair et le thème sombre.
            </p>
          </div>
          <button
            type="button"
            onClick={toggleTheme}
            className="flex shrink-0 items-center gap-2 rounded-full border border-border/80 px-4 py-2 text-xs font-semibold text-foreground transition-colors hover:bg-muted/60"
          >
            {theme === "dark" ? (
              <Sun className="w-4 h-4" />
            ) : (
              <Moon className="w-4 h-4" />
            )}
            {theme === "dark" ? "Thème clair" : "Thème sombre"}
          </button>
        </CardContent>
      </Card>

      {/* CV de référence card */}
      <Card>
        <CardContent className="p-6 space-y-4">
          <h3 className="text-base font-bold font-display text-foreground">
            CV de référence
          </h3>
          <p className="text-xs text-muted-foreground">
            Ce CV servira de base à l'IA pour postuler automatiquement et analyser les opportunités.
          </p>

          <div
            onClick={() => fileInputRef.current?.click()}
            className="border-2 border-dashed border-border/80 hover:border-primary/50 rounded-2xl p-6 text-center cursor-pointer transition-all flex flex-col items-center justify-center gap-2 hover:bg-muted/30"
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.docx"
              className="hidden"
              onChange={(e) => {
                if (e.target.files?.[0]) handleCvUpload(e.target.files[0]);
              }}
            />

            <div className="w-10 h-10 rounded-xl bg-primary/10 text-primary flex items-center justify-center">
              <UploadCloud className="w-5 h-5" />
            </div>

            {profile?.has_cv ? (
              <div>
                <p className="text-sm font-bold text-foreground flex items-center justify-center gap-1.5">
                  <FileCheck2 className="w-4 h-4 text-success" />
                  {profile.cv_filename || "CV enregistré"}
                </p>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Mis à jour le {formatDate(profile.updated_at)} · Cliquez pour remplacer
                </p>
              </div>
            ) : (
              <div>
                <p className="text-xs font-semibold text-foreground">
                  {isUploadingCv ? "Téléversement et analyse..." : "Téléverser mon CV de référence"}
                </p>
                <p className="text-[11px] text-muted-foreground">
                  Format PDF ou DOCX (Max 5 Mo)
                </p>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Profile details form */}
      <Card>
        <CardContent className="p-6">
          <form onSubmit={handleSaveProfile} className="space-y-5">
            <h3 className="text-base font-bold font-display text-foreground mb-4">
              Informations personnelles
            </h3>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Input
                label="Prénom"
                placeholder="ex: Thomas"
                value={firstName}
                onChange={(e) => setFirstName(e.target.value)}
                required
              />

              <Input
                label="Nom"
                placeholder="ex: Martin"
                value={lastName}
                onChange={(e) => setLastName(e.target.value)}
                required
              />

              <Input
                label="Numéro de téléphone"
                placeholder="ex: +33 6 12 34 56 78"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                required
                icon={<Phone className="w-4 h-4" />}
              />

              <Input
                label="Adresse ou Ville"
                placeholder="ex: Paris, France"
                value={address}
                onChange={(e) => setAddress(e.target.value)}
                icon={<MapPin className="w-4 h-4" />}
              />

              <Input
                label="Prétentions salariales (FCFA / mois)"
                placeholder="ex: 150k-300k FCFA / mois"
                value={salaryExpectation}
                onChange={(e) => setSalaryExpectation(e.target.value)}
                icon={<Banknote className="w-4 h-4" />}
              />

              <Input
                label="Profil LinkedIn (URL)"
                placeholder="https://linkedin.com/in/..."
                value={linkedinUrl}
                onChange={(e) => setLinkedinUrl(e.target.value)}
                icon={<Linkedin className="w-4 h-4" />}
              />

              <Input
                label="Portfolio / Site web (URL)"
                placeholder="https://mon-portfolio.com"
                value={portfolioUrl}
                onChange={(e) => setPortfolioUrl(e.target.value)}
                icon={<Globe className="w-4 h-4" />}
              />

              <div className="col-span-full">
                <Select
                  label="Autorisation de travail"
                  options={WORK_AUTHORIZATIONS}
                  value={workAuth}
                  onChange={(e) => setWorkAuth(e.target.value)}
                />
              </div>
            </div>

            <div className="flex justify-end pt-4">
              <Button
                type="submit"
                variant="primary"
                isLoading={isSaving}
                icon={<Save className="w-4 h-4" />}
              >
                Enregistrer mon profil
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      {/* Search preferences - collected at onboarding, editable here too */}
      <Card>
        <CardContent className="p-6 space-y-6">
          <div>
            <h3 className="text-base font-bold font-display text-foreground">
              Préférences de recherche
            </h3>
            <p className="text-xs text-muted-foreground mt-1">
              Ces critères pilotent le tri et le ranking des offres qui vous
              sont proposées.
            </p>
          </div>

          <StepJobTitles
            desiredJobTitles={desiredJobTitles}
            onDesiredJobTitlesChange={setDesiredJobTitles}
            seniorityLevel={seniorityLevel}
            onSeniorityLevelChange={setSeniorityLevel}
          />

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

          <div className="space-y-3">
            <label className="block text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Objectif de candidatures par semaine
            </label>
            <div className="flex items-center gap-4">
              <input
                type="range"
                min={1}
                max={50}
                value={weeklyGoal}
                onChange={(e) => setWeeklyGoal(Number(e.target.value))}
                className="h-1.5 flex-1 cursor-pointer appearance-none rounded-full bg-muted accent-primary [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-primary"
              />
              <span className="w-16 shrink-0 rounded-lg bg-primary/10 py-1.5 text-center font-display text-sm font-bold text-primary">
                {weeklyGoal}/sem.
              </span>
            </div>
          </div>

          <div className="flex justify-end pt-2">
            <Button
              type="button"
              variant="primary"
              isLoading={isSavingPrefs}
              icon={<Save className="w-4 h-4" />}
              onClick={handleSavePreferences}
            >
              Enregistrer mes préférences
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Monthly LLM usage (beta) */}
      <Card>
        <CardContent className="p-6">
          <UsageGauges />
        </CardContent>
      </Card>

      {/* Account-level export + deletion (RGPD) */}
      <Card>
        <CardContent className="p-6">
          <DangerZone />
        </CardContent>
      </Card>

      {/* Delete Profile Confirmation Dialog */}
      <Dialog
        isOpen={isDeleteOpen}
        onClose={() => setIsDeleteOpen(false)}
        title="Supprimer les informations du profil"
        description="Cette action effacera vos coordonnées et votre CV de référence de la plateforme."
      >
        <div className="flex justify-end gap-2 pt-4">
          <Button variant="ghost" onClick={() => setIsDeleteOpen(false)}>
            Annuler
          </Button>
          <Button
            variant="danger"
            isLoading={isDeleting}
            onClick={handleDeleteProfile}
          >
            Confirmer la suppression
          </Button>
        </div>
      </Dialog>
    </div>
  );
}
