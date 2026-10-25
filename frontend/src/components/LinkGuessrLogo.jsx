// Icône LinkGuessr (concept « Path ») : départ cyan, deux nœuds creux (les liens à deviner), arrivée violette.
// Les couleurs suivent le thème via --logo-ink, --logo-a et --logo-b (index.css). Ni dégradé, ni glow, ni animation.
export default function LinkGuessrLogo({ size = 32, className, decorative = true }) {
  return (
    <svg
      viewBox="0 0 100 100"
      width={size}
      height={size}
      className={className}
      {...(decorative ? { "aria-hidden": "true", focusable: "false" } : { role: "img", "aria-label": "LinkGuessr" })}
    >
      <g fill="none" strokeLinecap="round" strokeLinejoin="round" style={{ stroke: "var(--logo-ink, #F0F4FF)" }}>
        <path d="M22 76 L36.32 50.54 M46.15 48.3 L53.85 53.7 M63.51 51.37 L78 24" strokeWidth="8" strokeLinecap="butt" />
        <circle cx="40" cy="44" r="7.5" strokeWidth="6" />
        <circle cx="60" cy="58" r="7.5" strokeWidth="6" />
      </g>
      <circle cx="22" cy="76" r="13" style={{ fill: "var(--logo-a, #00D9FF)" }} />
      <circle cx="78" cy="24" r="13" style={{ fill: "var(--logo-b, #8B5CF6)" }} />
    </svg>
  );
}
