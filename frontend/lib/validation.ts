export const MAX_CV_SIZE_BYTES = 5 * 1024 * 1024;

const ALLOWED_EXTENSIONS = [".pdf", ".docx"];

export function validateCvFile(file: File): string | null {
  const lowerName = file.name.toLowerCase();
  const hasAllowedExtension = ALLOWED_EXTENSIONS.some((ext) => lowerName.endsWith(ext));
  if (!hasAllowedExtension) {
    return "Format de fichier non supporté. Utilisez un PDF ou un DOCX.";
  }
  if (file.size > MAX_CV_SIZE_BYTES) {
    return "Le fichier dépasse la taille maximale autorisée (5 Mo).";
  }
  return null;
}
