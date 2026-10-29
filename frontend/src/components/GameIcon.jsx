// Pictogrammes des jeux, dans le style du logo (traits ronds, nœuds) ; couleur via currentColor.
const PATHS = {
  // Loupe posée sur un petit réseau
  explore: (
    <>
      <path d="M18 70 L34 52 M34 52 L52 60" />
      <circle cx="18" cy="70" r="6" fill="currentColor" stroke="none" />
      <circle cx="34" cy="52" r="6" />
      <circle cx="58" cy="40" r="20" />
      <path d="M73 55 L86 68" strokeWidth="9" />
    </>
  ),
  // Chemin dont le nœud du milieu est un point d'interrogation
  guesswho: (
    <>
      <path d="M22 74 L36 60 M64 40 L78 26" />
      <circle cx="22" cy="74" r="8" fill="currentColor" stroke="none" />
      <circle cx="78" cy="26" r="8" fill="currentColor" stroke="none" />
      <circle cx="50" cy="50" r="16" strokeDasharray="6 6" />
      <path d="M45 45 Q45 39 50 39 Q56 39 56 45 Q56 49 50 51 L50 54" strokeWidth="5" />
      <circle cx="50" cy="60" r="2.5" fill="currentColor" stroke="none" />
    </>
  ),
  // Sauts successifs vers une cible
  relay: (
    <>
      <path d="M18 72 Q28 52 40 62 Q52 72 60 50 Q66 34 76 30" />
      <circle cx="18" cy="72" r="7" fill="currentColor" stroke="none" />
      <circle cx="40" cy="62" r="5" />
      <circle cx="60" cy="50" r="5" />
      <circle cx="78" cy="28" r="12" />
      <circle cx="78" cy="28" r="4" fill="currentColor" stroke="none" />
    </>
  ),
  // Trois joueurs reliés autour d'un éclair (direct)
  live: (
    <>
      <path d="M26 30 L50 50 L74 30 M50 50 L50 78" />
      <circle cx="26" cy="30" r="9" fill="currentColor" stroke="none" />
      <circle cx="74" cy="30" r="9" fill="currentColor" stroke="none" />
      <circle cx="50" cy="80" r="9" fill="currentColor" stroke="none" />
      <path d="M54 38 L44 52 L56 52 L46 66" strokeWidth="5" />
    </>
  ),
  // Chronomètre
  count: (
    <>
      <circle cx="50" cy="56" r="28" />
      <path d="M50 56 L50 40 M50 56 L61 63" />
      <path d="M42 18 L58 18 M50 18 L50 28" />
      <path d="M74 30 L80 24" />
    </>
  ),
};

export default function GameIcon({ game, size = 48, className }) {
  return (
    <svg viewBox="0 0 100 100" width={size} height={size} className={className} aria-hidden="true" focusable="false"
      fill="none" stroke="currentColor" strokeWidth="6" strokeLinecap="round" strokeLinejoin="round">
      {PATHS[game]}
    </svg>
  );
}
