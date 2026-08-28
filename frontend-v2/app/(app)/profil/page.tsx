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
  Euro,
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import {
  getCandidateProfile,
  updateCandidateProfile,
  uploadReferenceCv,
  deleteProfile,
} from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Card, CardContent } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { Dialog } from "@/components/ui/Dialog";
import {
  cn,
  formatDate,
  isValidCvFile,
  MAX_FILE_SIZE,
} from "@/lib/utils";
import type { CandidateProfileOut } from "@/lib/types";

const WORK_AUTHORIZATIONS = [
  { value: "french_citizen", label: "Nationalité française / Citoyen UE" },
  { value: "visa_required", label: "Visa de travail requis" },
  { value: "work_permit", label: "Titre de séjour / Autorisation valide" },
];

export default function ProfilPage() {
  const { token, user } = useAuth();

  const [profile, setProfile] = useState<CandidateProfileOut | null>(null);
  const [fullName, setFullName] = useState("");
  const [phone, setPhone] = useState("");
  const [address, setAddress] = useState("");
  const [linkedinUrl, setLinkedinUrl] = useState("");
  const [portfolioUrl, setPortfolioUrl] = useState("");
  const [workAuth, setWorkAuth] = useState("french_citizen");
  const [salaryExpectation, setSalaryExpectation] = useState("");

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
        setFullName(res.full_name || "");
        setPhone(res.phone || "");
        setAddress(res.address || "");
        setLinkedinUrl(res.linkedin_url || "");
        setPortfolioUrl(res.portfolio_url || "");
        setWorkAuth(res.work_authorization || "french_citizen");
        setSalaryExpectation(res.salary_expectation || "");
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
        full_name: fullName,
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
      setFullName("");
      setPhone("");
      setAddress("");
      setLinkedinUrl("");
      setPortfolioUrl("");
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
                label="Nom complet"
                placeholder="ex: Thomas Martin"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
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
                label="Prétentions salariales (€)"
                placeholder="ex: 55k-60k€"
                value={salaryExpectation}
                onChange={(e) => setSalaryExpectation(e.target.value)}
                icon={<Euro className="w-4 h-4" />}
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
