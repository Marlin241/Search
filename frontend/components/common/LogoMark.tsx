/**
 * La marque de Search : une arche — le seuil qu'on franchit pour décrocher
 * un poste, avec un clin d'œil aux portes monumentales de Dakar — traversée
 * d'une flèche montante. Un seul trait, une seule couleur (`currentColor`),
 * pensée pour rester lisible de 16 à 96 px et s'inverser clair / sombre.
 */
export function LogoMark({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 32 32"
      fill="none"
      className={className}
      aria-hidden="true"
    >
      <path
        d="M6.5 26.5 L6.5 15 C6.5 9.2 10.8 5 16 5 C21.2 5 25.5 9.2 25.5 15 L25.5 26.5"
        stroke="currentColor"
        strokeWidth="4"
        strokeLinecap="round"
      />
      <path
        d="M16 24.5 L16 11.4"
        stroke="currentColor"
        strokeWidth="4"
        strokeLinecap="round"
      />
      <path
        d="M11.3 15.8 L16 10.7 L20.7 15.8"
        stroke="currentColor"
        strokeWidth="4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
