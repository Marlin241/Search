import { PARENT_NAME, PARENT_URL, CONTACT_EMAIL } from "@/lib/brand";

export function MarketingFooter() {
  return (
    <footer className="border-t border-border/60 bg-card">
      <div className="mx-auto flex max-w-6xl flex-col gap-3 px-4 py-8 text-xs text-muted-foreground sm:flex-row sm:items-center sm:justify-between sm:px-6">
        <p>
          Un produit{" "}
          <a
            href={PARENT_URL}
            className="font-medium text-foreground hover:underline"
            target="_blank"
            rel="noopener noreferrer"
          >
            {PARENT_NAME}
          </a>{" "}
          · Version beta
        </p>
        <nav className="flex flex-wrap gap-x-4 gap-y-1">
          <a href="/conditions" className="hover:underline">
            Conditions d&apos;utilisation
          </a>
          <a href="/confidentialite" className="hover:underline">
            Politique de confidentialité
          </a>
          <a href={`mailto:${CONTACT_EMAIL}`} className="hover:underline">
            Contact
          </a>
        </nav>
      </div>
    </footer>
  );
}
