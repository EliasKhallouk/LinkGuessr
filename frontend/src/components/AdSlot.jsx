export default function AdSlot() {
  const handleClick = () => {
    try { window.dispatchEvent(new CustomEvent("ad:click", { detail: { slot: "sidebar" } })); } catch {}
    // Optional: integrate with your analytics here
    if (import.meta.env.DEV) {
      // eslint-disable-next-line no-console
      console.log("Ad clicked: sidebar");
    }
  };
  return (
    <aside className="ad-slot" aria-label="Advertisement">
      <div className="ad-inner" onClick={handleClick}>
        <span className="ad-badge">AD</span>
        <div className="ad-content">
          {/* Placeholder for Google AdSense snippet */}
          <p className="muted" style={{ margin: 0 }}>Espace publicitaire</p>
        </div>
      </div>
    </aside>
  );
}
