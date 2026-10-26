// Confettis de victoire, sans dépendance : une salve sur un canvas temporaire, aux couleurs du logo.
// Rien ne s'affiche si l'utilisateur a demandé à réduire les animations.
export function confetti() {
  if (typeof window === "undefined" || window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return;
  const css = getComputedStyle(document.documentElement);
  const colors = ["--logo-a", "--logo-b", "--accent-success", "--logo-ink"].map((v) => css.getPropertyValue(v).trim()).filter(Boolean);

  const canvas = document.createElement("canvas");
  canvas.className = "confetti-canvas";
  canvas.setAttribute("aria-hidden", "true");
  document.body.appendChild(canvas);
  const ratio = window.devicePixelRatio || 1;
  const width = window.innerWidth;
  const height = window.innerHeight;
  canvas.width = width * ratio;
  canvas.height = height * ratio;
  const ctx = canvas.getContext("2d");
  ctx.scale(ratio, ratio);

  const LIFE = 150; // images (~2,5 s)
  const pieces = Array.from({ length: 140 }, () => {
    const angle = -Math.PI / 2 + (Math.random() - 0.5) * 1.6;
    const speed = 7 + Math.random() * 9;
    return {
      x: width / 2, y: height * 0.4,
      vx: Math.cos(angle) * speed, vy: Math.sin(angle) * speed,
      w: 6 + Math.random() * 5, h: 9 + Math.random() * 6,
      rot: Math.random() * Math.PI, spin: (Math.random() - 0.5) * 0.3,
      color: colors[Math.floor(Math.random() * colors.length)],
    };
  });

  let frame = 0;
  const tick = () => {
    frame += 1;
    ctx.clearRect(0, 0, width, height);
    ctx.globalAlpha = Math.min(1, (LIFE - frame) / 30);
    for (const p of pieces) {
      p.vx *= 0.985;
      p.vy = p.vy * 0.985 + 0.35;
      p.x += p.vx;
      p.y += p.vy;
      p.rot += p.spin;
      ctx.save();
      ctx.translate(p.x, p.y);
      ctx.rotate(p.rot);
      ctx.fillStyle = p.color;
      ctx.fillRect(-p.w / 2, -p.h / 2, p.w, p.h * Math.abs(Math.cos(p.rot * 2)));
      ctx.restore();
    }
    if (frame < LIFE) requestAnimationFrame(tick);
    else canvas.remove();
  };
  requestAnimationFrame(tick);
}
