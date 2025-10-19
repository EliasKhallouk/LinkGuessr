import "./App.css";
import Game from "./components/Game";
import Graph from "./components/Graph";

function App() {
  return (
    <div className="app-shell">
      <header className="header">
        <div className="brand">
          <span className="logo-dot" />
          <h1 className="title">LinkGuessr</h1>
        </div>
        <p className="tagline">Devinez le chemin le plus court entre deux personnes</p>
      </header>

      <main className="grid">
        <Graph />
        <Game />
      </main>

      <footer className="footer">
        <span>© {new Date().getFullYear()} LinkGuessr - Elias Khallouk</span>
      </footer>
    </div>
  );
}

export default App;
