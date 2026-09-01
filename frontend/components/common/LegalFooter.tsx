import { CONTACT_EMAIL } from "@/lib/brand";

export function LegalFooter() {
  return (
    <footer className="mt-8 text-center text-xs text-muted-foreground space-x-3">
      <a href="/conditions" className="hover:underline">
        Conditions d&apos;utilisation
      </a>
      <span>·</span>
      <a href="/confidentialite" className="hover:underline">
        Politique de confidentialité
      </a>
      <span>·</span>
      <a
        href={`mailto:${CONTACT_EMAIL}`}
        className="hover:underline"
      >
        Contact
      </a>
    </footer>
  );
}
