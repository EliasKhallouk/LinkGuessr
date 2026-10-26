import ConnectRelay from "./components/ConnectRelay";
import Game from "./components/Game";
import GuessRelations from "./components/GuessRelations";
import GuessWhoPath from "./components/GuessWhoPath";
import Leaderboard from "./components/Leaderboard";

// Les jeux de l'accueil, dans l'ordre des cartes. Textes : games.<key>.* dans les traductions.
export const GAMES = [
  { key: "explore", path: "/explorer", element: <Game /> },
  { key: "guesswho", path: "/qui-est-cache", element: <GuessWhoPath /> },
  { key: "relay", path: "/relier", element: <ConnectRelay /> },
  { key: "count", path: "/combien", element: <><GuessRelations /><Leaderboard /></> },
];

export const gamePath = (key) => GAMES.find((g) => g.key === key)?.path ?? "/";
